"""Detection expander abstractions: the port and a shared search template."""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from piighost.models import Detection, Span


@runtime_checkable
class AnyDetectionExpander(Protocol):
    """A component that finds occurrences a detector missed.

    Given the detections found so far and the source text, it returns them plus
    new detections for occurrences of the same values that were not detected.
    This is useful when a NER misses a repeat of a name it flagged elsewhere.
    """

    def expand(self, text: str, detections: list[Detection]) -> list[Detection]:
        """Return the detections plus any missed occurrences of their values.

        Args:
            text: The source text the detections were found in.
            detections: The detections found so far.

        Returns:
            The original detections plus one for each missed occurrence.
        """
        ...


class BaseDetectionExpander(ABC):
    """Add missed occurrences of detected values, one detection at a time.

    The skeleton lives here: keep the original detections, then for each one ask
    the subclass where else its value occurs in the text and add a detection for
    every occurrence not already covered, carrying the source detection's label
    and confidence. A subclass defines _find_occurrences, the only step that
    varies, the rule that locates a value's occurrences, such as whole-word
    matching.
    """

    def expand(self, text: str, detections: list[Detection]) -> list[Detection]:
        """Return the detections plus any missed occurrences of their values."""
        expanded = list(detections)
        seen = {detection.span for detection in detections}

        for detection in detections:
            for span in self._find_occurrences(text, detection):
                if span in seen:
                    continue
                found = Detection(
                    span=span,
                    text=span.extract(text),
                    label=detection.label,
                    confidence=detection.confidence,
                )
                expanded.append(found)
                seen.add(span)

        return expanded

    @abstractmethod
    def _find_occurrences(self, text: str, detection: Detection) -> Iterable[Span]:
        """Return the spans in text where the detection's value occurs."""
        ...
