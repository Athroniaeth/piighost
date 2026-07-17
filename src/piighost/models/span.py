"""Character-offset span primitive.

A Span is a half-open interval [start, end) over a string, mirroring Python
slice semantics such as text[start:end]. It is the geometric foundation shared
by the detection and replacement stages, so its invariants are kept strict and
its arithmetic total.
"""

from dataclasses import dataclass
from typing import Self

from piighost.exceptions import NegativeSpanStartError, SpanOrderingError


@dataclass(frozen=True, slots=True, order=True)
class Span:
    """A half-open character range [start, end) within some text.

    The dataclass is ordered by (start, end) so a list of spans sorts
    left-to-right, which is what the replacement stage relies on to apply
    edits without shifting offsets it has not processed yet.

    Attributes:
        start: Inclusive start offset. Must be >= 0.
        end: Exclusive end offset. Must be > start.

    Raises:
        NegativeSpanStartError: If start is negative.
        SpanOrderingError: If end is not strictly greater than start (an empty
            or reversed range). Empty spans are rejected because a PII
            detection always covers at least one character. Relax this only if
            insertion points ever become a real need.
    """

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0:
            raise NegativeSpanStartError(f"Span start must be >= 0, got {self.start}")

        if self.end <= self.start:
            raise SpanOrderingError(
                f"Span end must be > start, got start={self.start}, end={self.end}"
            )

    @property
    def length(self) -> int:
        """Number of characters the span covers."""
        return self.end - self.start

    def __len__(self) -> int:
        return self.length

    def overlaps(self, other: Self) -> bool:
        """Whether self and other share at least one character.

        Half-open semantics mean adjacent spans such as [0, 5) and [5, 10) do
        not overlap.
        """
        return self.start < other.end and other.start < self.end

    def contains(self, other: Self) -> bool:
        """Whether other is fully enclosed by self."""
        return self.start <= other.start and other.end <= self.end

    def shift(self, offset: int) -> Self:
        """Return a copy translated by offset characters.

        Used to remap a span found on normalized text back onto the original
        text. A shift that would push start below zero raises via the
        constructor, surfacing the bug rather than silently clamping.
        """
        return Span(
            self.start + offset,
            self.end + offset,
        )

    def extract(self, text: str) -> str:
        """Return the substring of text covered by this span."""
        return text[self.start : self.end]
