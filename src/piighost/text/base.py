"""Splitter port: the contract every text splitter satisfies."""

from typing import Protocol, runtime_checkable

from piighost.models import Chunk


@runtime_checkable
class AnySplitter(Protocol):
    """A component that splits a text into offset-aware chunks.

    Implementations decide how to cut the text, by character, token, or
    sentence. Every returned chunk carries its start offset in the original
    text, so a detection found in a chunk can be remapped with Span.shift.
    """

    def split(self, text: str) -> list[Chunk]:
        """Split text into chunks that carry their original offsets.

        Args:
            text: The text to split.

        Returns:
            The chunks, in order, each a contiguous slice of the original text.
        """
        ...
