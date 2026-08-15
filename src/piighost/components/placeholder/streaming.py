"""Streaming-safe rewriting of delimited placeholder tokens.

A model may stream its reply in fragments that split a placeholder down the
middle, so <<PERSON:1>> arrives as <<PER then SON:1>>. Rewriting each fragment on
its own would corrupt the token. The decoders here buffer just enough to keep
tokens whole across fragments, rewriting each token once it completes. A sync
decoder rewrites with a plain callback; an async decoder awaits its callback, so
a pipeline-backed or remote deanonymization can drive streaming restoration.

Both decoders share one scan of the buffer, so the token grammar and the rule
for how much to hold back never diverge between them.
"""

import re
from collections.abc import Awaitable, Callable
from typing import NamedTuple

DEFAULT_PREFIX = "<<"
"""Default opening delimiter wrapped around a placeholder token."""

DEFAULT_SUFFIX = ">>"
"""Default closing delimiter wrapped around a placeholder token."""


def compile_token_pattern(prefix: str, suffix: str) -> re.Pattern[str]:
    """Compile the regex matching delimited tokens, capturing the inner form.

    It matches the delimiters around a non-empty, non-greedy inner run, so it
    recognizes tokens structurally without validating the inner shape. Shared by
    the factory recognition helpers and the stream decoders so the three never
    diverge on the token grammar.
    """
    regex_prefix = re.escape(prefix)
    regex_suffix = re.escape(suffix)
    return re.compile(regex_prefix + r"(.+?)" + regex_suffix)


class _Segment(NamedTuple):
    """A slice of the buffer that a decoder emits.

    Attributes:
        text: The slice's text, either a literal run or a whole token.
        is_token: Whether the slice is a complete token needing replacement.
    """

    text: str
    is_token: bool


def _held_length(buffer: str, prefix: str) -> int:
    """Return how many trailing chars could still grow into a token.

    Assumes the buffer holds no complete token, the split having drained them
    first. A full opening delimiter with no close holds everything from it on;
    otherwise a trailing fragment of the opening delimiter is held so a delimiter
    split across fragments still lines up.
    """
    opening = buffer.find(prefix)
    if opening != -1:
        return len(buffer) - opening

    for size in range(len(prefix) - 1, 0, -1):
        if buffer.endswith(prefix[:size]):
            return size
    return 0


def _split_buffer(
    buffer: str,
    pattern: re.Pattern[str],
    prefix: str,
) -> tuple[list[_Segment], str]:
    """Split a buffer into ordered segments to emit and the tail to hold back.

    Drains every complete token, splitting the text around each into a literal
    segment then a token segment, then holds back the trailing run that could
    still grow into a token and emits the rest as a final literal segment. Side
    effect free, so the sync and async decoders share one definition of the
    token grammar and the holding rule, differing only in how they replace a
    token segment.
    """
    segments: list[_Segment] = []
    remaining = buffer

    match = pattern.search(remaining)
    while match is not None:
        before = remaining[: match.start()]
        token = match.group()
        segments.append(_Segment(text=before, is_token=False))
        segments.append(_Segment(text=token, is_token=True))
        remaining = remaining[match.end() :]
        match = pattern.search(remaining)

    held = _held_length(remaining, prefix)
    boundary = len(remaining) - held
    safe = remaining[:boundary]
    tail = remaining[boundary:]
    segments.append(_Segment(text=safe, is_token=False))
    return segments, tail


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
        prefix: str = DEFAULT_PREFIX,
        suffix: str = DEFAULT_SUFFIX,
    ) -> None:
        """Store the delimiters and the per-token replacement callback."""
        self.prefix = prefix
        self.suffix = suffix
        self._replace = replace
        self._pattern = compile_token_pattern(prefix, suffix)
        self._buffer = ""

    def feed(self, chunk: str) -> str:
        """Absorb a fragment and return the text that is now safe to emit."""
        emitted: list[str] = []
        self._buffer += chunk

        segments, self._buffer = _split_buffer(self._buffer, self._pattern, self.prefix)
        for segment in segments:
            if segment.is_token:
                replaced = self._replace(segment.text)
                emitted.append(replaced)
            else:
                emitted.append(segment.text)
        return "".join(emitted)

    def flush(self) -> str:
        """Release the buffered tail once the stream is over."""
        remainder = self._buffer
        self._buffer = ""
        return remainder


class AsyncPlaceholderStreamDecoder:
    """Rewrite delimited placeholder tokens across an async token stream.

    The async twin of PlaceholderStreamDecoder: it holds fragments the same way,
    but awaits its replace callback for each completed token, so a pipeline or a
    remote client whose deanonymization is a coroutine can rewrite tokens as they
    stream. The callback is awaited once per completed token, with the whole
    token as its argument, and a token the callback returns unchanged is emitted
    as it stood, so invented-token handling stays the caller's concern.

    Attributes:
        prefix: The opening delimiter of a token.
        suffix: The closing delimiter of a token.
    """

    def __init__(
        self,
        replace: Callable[[str], Awaitable[str]],
        prefix: str = DEFAULT_PREFIX,
        suffix: str = DEFAULT_SUFFIX,
    ) -> None:
        """Store the delimiters and the awaitable per-token replacement callback."""
        self.prefix = prefix
        self.suffix = suffix
        self._replace = replace
        self._pattern = compile_token_pattern(prefix, suffix)
        self._buffer = ""

    async def feed(self, chunk: str) -> str:
        """Absorb a fragment and return the text that is now safe to emit."""
        emitted: list[str] = []
        self._buffer += chunk

        segments, self._buffer = _split_buffer(self._buffer, self._pattern, self.prefix)
        for segment in segments:
            if segment.is_token:
                replaced = await self._replace(segment.text)
                emitted.append(replaced)
            else:
                emitted.append(segment.text)
        return "".join(emitted)

    def flush(self) -> str:
        """Release the buffered tail once the stream is over.

        The tail is an incomplete token or a partial opening delimiter, so it
        holds nothing to replace and is released as it stood.
        """
        remainder = self._buffer
        self._buffer = ""
        return remainder
