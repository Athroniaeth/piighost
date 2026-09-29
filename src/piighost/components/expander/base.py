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

    An occurrence that overlaps a character already covered is skipped. The
    expander runs after the overlap resolver, so nothing reconciles what it
    adds, and the renderer refuses overlapping spans. "Paul" found inside a
    kept "Monsieur Paul" is already hidden. Values are searched longest first,
    so where "Paul Lemoine" and "Paul" occur at one place the full name is the
    one added.
    """

    def expand(self, text: str, detections: list[Detection]) -> list[Detection]:
        """Return the detections plus any missed occurrences of their values."""
        expanded = list(detections)
        covered = bytearray(len(text))
        for detection in detections:
            _cover(covered, detection.span)

        longest_first = sorted(detections, key=lambda d: len(d.text), reverse=True)
        for detection in longest_first:
            for span in self._find_occurrences(text, detection):
                if _touches(covered, span):
                    continue
                found = Detection(
                    span=span,
                    text=span.extract(text),
                    label=detection.label,
                    confidence=detection.confidence,
                )
                expanded.append(found)
                _cover(covered, span)

        return expanded

    @abstractmethod
    def _find_occurrences(self, text: str, detection: Detection) -> Iterable[Span]:
        """Return the spans in text where the detection's value occurs."""
        ...


def _cover(covered: bytearray, span: Span) -> None:
    """Mark the characters of a span as covered by a kept detection."""
    covered[span.start : span.end] = b"\x01" * (span.end - span.start)


def _touches(covered: bytearray, span: Span) -> bool:
    """Whether any character of the span is already covered by a kept detection."""
    return covered.find(1, span.start, span.end) != -1
