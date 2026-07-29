"""Detection model: a labeled, scored span of text."""

from dataclasses import dataclass
from typing import Any, Self

from piighost.exceptions import ConfidenceError
from piighost.models.span import Span


@dataclass(frozen=True, slots=True, order=True)
class Detection:
    """A single PII detection, a span carrying a label, a confidence, and the
    matched text.

    Ordered by (span, text, label, confidence) so detections sort by position
    first, which the span-conflict stage relies on.

    Attributes:
        span: Where the detection sits in the text, as a half-open range.
        text: The matched substring.
        label: The PII category, for example PERSON or EMAIL.
        confidence: Detector confidence, in the closed range 0 to 1.

    Raises:
        ConfidenceError: If confidence is outside the range 0 to 1.
    """

    span: Span
    text: str
    label: str
    confidence: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ConfidenceError(
                f"Detection confidence must be in [0, 1], got {self.confidence}"
            )

    def overlaps(self, other: Self) -> bool:
        """Whether this detection's span overlaps the other's."""
        return self.span.overlaps(other.span)

    def to_dict(self) -> dict[str, str | int | float]:
        """Return the detection as a flat, JSON-ready dict.

        The span is flattened into start and end, so the shape is one level that
        a store or wire format can serialize without knowing the model.
        """
        return {
            "start": self.span.start,
            "end": self.span.end,
            "text": self.text,
            "label": self.label,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Rebuild a detection from the flat dict produced by to_dict."""
        return cls(
            span=Span(data["start"], data["end"]),
            text=data["text"],
            label=data["label"],
            confidence=data["confidence"],
        )
