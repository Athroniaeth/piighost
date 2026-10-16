"""Entity model: a group of detections that refer to the same PII value."""

from dataclasses import dataclass

from piighost.exceptions import EmptyEntityError
from piighost.models.detection import Detection
from piighost.models.span import Span


@dataclass(frozen=True, slots=True)
class Entity:
    """A group of detections identified as the same PII value.

    Every occurrence of the value across the text is one detection. The group
    shares a single placeholder and deanonymizes to a single value. The label,
    canonical text, and spans are derived from the detections rather than
    stored, so nothing can drift out of sync and the value is not duplicated.
    The detections may carry different labels, since two detectors can name one
    value differently; the entity takes the label of its first detection, so a
    later detection under another label never renames a token already issued.

    Attributes:
        detections: The occurrences the entity groups, at least one, in
            first-occurrence order.

    Raises:
        EmptyEntityError: If no detections are given.
    """

    detections: tuple[Detection, ...]

    def __post_init__(self) -> None:
        """Reject an empty detection set."""
        if not self.detections:
            raise EmptyEntityError("An Entity needs at least one detection")

    @property
    def label(self) -> str:
        """The PII label, the one its first detection carries."""
        return self.detections[0].label

    @property
    def text(self) -> str:
        """The canonical value, taken from the first occurrence."""
        return self.detections[0].text

    @property
    def spans(self) -> tuple[Span, ...]:
        """The span of every occurrence, in detection order."""
        return tuple(detection.span for detection in self.detections)
