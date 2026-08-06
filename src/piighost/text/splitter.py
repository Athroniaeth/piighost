"""Recursive character text splitter that tracks original offsets.

The separator-hierarchy logic follows LangChain's RecursiveCharacterTextSplitter:
split on paragraphs, then lines, then words, then characters, preferring the
coarsest boundary that keeps a chunk under the size limit. Unlike a RAG splitter,
each chunk here carries its start offset in the original text and its text is a
contiguous slice of the original, so a detection found in a chunk remaps to the
original text with Span.shift.
"""

import re

from piighost.models import Chunk

DEFAULT_SEPARATORS = ["\n\n", "\n", " ", ""]
"""Separator hierarchy tried in order, from paragraph down to character."""


class RecursiveCharacterTextSplitter:
    """Split long text into overlapping chunks, preserving original offsets.

    It works in two passes. First it cuts the text into small pieces, trying the
    separators in order (paragraph, line, word, character) and descending to a
    finer separator only when a piece is still larger than chunk_size. Then it
    packs consecutive pieces into chunks, overlapping consecutive chunks by about
    chunk_overlap so an entity sitting on a boundary is still seen whole in one
    chunk.

    Two rules govern the packing:

    - chunk_size is a hard limit, always respected, unless a single indivisible
      piece is itself larger than it. With the default separators, which reach
      the character level, that never happens.
    - chunk_overlap is best effort. Forward progress always wins, so when a
      chunk is a single piece with nothing to reach back into, the overlap is
      reduced or skipped rather than looping.

    Attributes:
        chunk_size: The maximum length of a chunk, in characters.
        chunk_overlap: The overlap between consecutive chunks, in characters.
        separators: The separator hierarchy, tried in order.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 100,
        separators: list[str] | None = None,
    ) -> None:
        """Store the splitting parameters.

        Raises:
            ValueError: If chunk_size is not positive, or chunk_overlap is not
                smaller than chunk_size.
        """
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be positive, got {chunk_size}")

        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({chunk_overlap}) must be smaller than "
                f"chunk_size ({chunk_size})"
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or DEFAULT_SEPARATORS

    def split(self, text: str) -> list[Chunk]:
        """Split text into overlapping chunks that carry their offsets."""
        pieces = self._split_to_pieces(text, 0, len(text), self.separators)
        return self._merge(pieces, text)

    def _split_to_pieces(
        self,
        text: str,
        start: int,
        end: int,
        separators: list[str],
    ) -> list[tuple[int, int]]:
        """Recursively split text[start:end] into atomic offset ranges."""
        remaining: list[str] = []
        segment = text[start:end]
        separator = separators[-1]

        for index, candidate in enumerate(separators):
            if candidate == "":
                break
            if candidate in segment:
                separator = candidate
                remaining = separators[index + 1 :]
                break

        pieces: list[tuple[int, int]] = []
        for piece_start, piece_end in self._raw_split(text, start, end, separator):
            if piece_end - piece_start <= self.chunk_size or not remaining:
                pieces.append((piece_start, piece_end))
            else:
                pieces.extend(
                    self._split_to_pieces(
                        text,
                        piece_start,
                        piece_end,
                        remaining,
                    )
                )
        return pieces

    def _raw_split(
        self,
        text: str,
        start: int,
        end: int,
        separator: str,
    ) -> list[tuple[int, int]]:
        """Split text[start:end] on separator into content ranges, dropping it."""
        if separator == "":
            return [(index, index + 1) for index in range(start, end)]
        ranges: list[tuple[int, int]] = []
        cursor = start

        for match in re.finditer(re.escape(separator), text[start:end]):
            piece_start = start + match.start()
            piece_end = start + match.end()

            if piece_start > cursor:
                ranges.append((cursor, piece_start))

            cursor = piece_end

        if cursor < end:
            ranges.append((cursor, end))
        return ranges

    def _merge(
        self,
        pieces: list[tuple[int, int]],
        text: str,
    ) -> list[Chunk]:
        """Pack ordered ranges into overlapping chunks of at most chunk_size."""
        cursor = 0
        count = len(pieces)
        chunks: list[Chunk] = []

        while cursor < count:
            last = cursor
            window_start = pieces[cursor][0]

            while self._fits_window(pieces, last, count, window_start):
                last += 1

            if last == cursor:
                # A single piece larger than chunk_size: the one case a chunk
                # exceeds chunk_size, since a piece cannot be split further.
                last = cursor + 1

            window_end = pieces[last - 1][1]
            chunk_text = text[window_start:window_end]
            chunk = Chunk(text=chunk_text, start=window_start)
            chunks.append(chunk)

            if last >= count:
                break
            # Step back so the next window overlaps this one by about
            # chunk_overlap. Keeping back > cursor guarantees at least one piece
            # of forward progress, so overlap is skipped rather than looping when
            # a chunk is a single piece.
            back = last - 1
            while back > cursor and window_end - pieces[back][0] <= self.chunk_overlap:
                back -= 1
            cursor = back + 1
        return chunks

    def _fits_window(
        self, pieces: list[tuple[int, int]], last: int, count: int, window_start: int
    ) -> bool:
        """Whether piece last exists and keeps the window within chunk_size."""
        return last < count and pieces[last][1] - window_start <= self.chunk_size
