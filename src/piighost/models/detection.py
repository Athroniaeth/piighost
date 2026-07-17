"""Detection model: a labeled, scored span of text."""

from dataclasses import dataclass

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
