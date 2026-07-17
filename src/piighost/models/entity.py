"""Entity model: a group of detections that refer to the same PII value."""

from dataclasses import dataclass

from piighost.exceptions import EmptyEntityError, MixedLabelError
from piighost.models.detection import Detection
from piighost.models.span import Span


@dataclass(frozen=True, slots=True)
class Entity:
    """A group of detections identified as the same PII value.

    Every occurrence of the value across the text is one detection. The group
    shares a single placeholder and deanonymizes to a single value. The label,
    canonical text, and spans are derived from the detections rather than
    stored, so nothing can drift out of sync and the value is not duplicated.

    Attributes:
        detections: The occurrences the entity groups, at least one, all
            sharing a label.

    Raises:
        EmptyEntityError: If no detections are given.
        MixedLabelError: If the detections do not all share one label.
    """

    detections: tuple[Detection, ...]

    def __post_init__(self) -> None:
        if not self.detections:
            raise EmptyEntityError("An Entity needs at least one detection")

        labels = {detection.label for detection in self.detections}

        if len(labels) > 1:
            raise MixedLabelError(
                f"An Entity's detections must share one label, got {sorted(labels)}"
            )

    @property
    def label(self) -> str:
        """The shared PII label of the grouped detections."""
        return self.detections[0].label

    @property
    def text(self) -> str:
        """The canonical value, taken from the first occurrence."""
        return self.detections[0].text

    @property
    def spans(self) -> tuple[Span, ...]:
        """The span of every occurrence, in detection order."""
        return tuple(detection.span for detection in self.detections)
