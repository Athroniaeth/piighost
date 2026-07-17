"""Chunk model: a contiguous slice of a larger text, with its offset."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Chunk:
    """A contiguous slice of a larger text, with its original offset.

    Attributes:
        text: The chunk substring, a slice of the original text.
        start: The offset of the chunk in the original text.
    """

    text: str
    start: int

    @property
    def end(self) -> int:
        """The exclusive end offset of the chunk in the original text."""
        return self.start + len(self.text)
