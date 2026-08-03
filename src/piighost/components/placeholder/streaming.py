"""Streaming-safe rewriting of delimited placeholder tokens.

A model may stream its reply in fragments that split a placeholder down the
middle, so <<PERSON:1>> arrives as <<PER then SON:1>>. Rewriting each fragment on
its own would corrupt the token. The decoder here buffers just enough to keep
tokens whole across fragments. This is a preparation for streaming
deanonymization; nothing wires it in yet.
"""

import re
from collections.abc import Callable


def compile_token_pattern(prefix: str, suffix: str) -> re.Pattern[str]:
    """Compile the regex matching delimited tokens, capturing the inner form.

    It matches the delimiters around a non-empty, non-greedy inner run, so it
    recognizes tokens structurally without validating the inner shape. Shared by
    the factory recognition helpers and the stream decoder so the two never
    diverge on the token grammar.
    """
    regex_prefix = re.escape(prefix)
    regex_suffix = re.escape(suffix)
    return re.compile(regex_prefix + r"(.+?)" + regex_suffix)


class PlaceholderStreamDecoder:
    """Rewrite delimited placeholder tokens across a token-by-token stream.

    Feed each streamed fragment to feed, which returns the text that is now safe
    to emit and holds back any trailing fragment that could still grow into a
    token, rewriting every token it completes with the replace callback. Call
    flush once the stream ends to release whatever stayed buffered.

    Holding is conservative: from the first opening delimiter that has not yet
    closed, every following character is held until the closing delimiter
    arrives, because until then it might belong to a token. A stream that opens a
    delimiter and never closes it therefore buffers until flush.

    Attributes:
        prefix: The opening delimiter of a token.
        suffix: The closing delimiter of a token.
    """

    def __init__(
        self,
        replace: Callable[[str], str],
        prefix: str = "<<",
        suffix: str = ">>",
    ) -> None:
        """Store the delimiters and the per-token replacement callback."""
        self.prefix = prefix
        self.suffix = suffix
        self._replace = replace
        self._pattern = compile_token_pattern(prefix, suffix)
        self._buffer = ""

    def feed(self, chunk: str) -> str:
        """Absorb a fragment and return the text that is now safe to emit."""
        self._buffer += chunk
        emitted: list[str] = []

        match = self._pattern.search(self._buffer)
        while match is not None:
            emitted.append(self._buffer[: match.start()])
            emitted.append(self._replace(match.group()))
            self._buffer = self._buffer[match.end() :]
            match = self._pattern.search(self._buffer)

        boundary = len(self._buffer) - self._held_length()
        emitted.append(self._buffer[:boundary])
        self._buffer = self._buffer[boundary:]
        return "".join(emitted)

    def flush(self) -> str:
        """Release the buffered tail once the stream is over."""
        remainder = self._buffer
        self._buffer = ""
        return remainder

    def _held_length(self) -> int:
        """Return how many trailing chars could still grow into a token.

        Assumes the buffer holds no complete token, feed having drained them
        first. A full opening delimiter with no close holds everything from it
        on; otherwise a trailing fragment of the opening delimiter is held so a
        delimiter split across fragments still lines up.
        """
        opening = self._buffer.find(self.prefix)
        if opening != -1:
            return len(self._buffer) - opening

        for size in range(len(self.prefix) - 1, 0, -1):
            if self._buffer.endswith(self.prefix[:size]):
                return size
        return 0
