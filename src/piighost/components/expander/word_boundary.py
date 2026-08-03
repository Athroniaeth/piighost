"""Word-boundary detection expander: find missed whole-word occurrences."""

import re

from piighost.models import Detection
from piighost.text import find_all_word_boundary


class WordBoundaryExpander:
    """Find occurrences a detector missed by whole-word text matching.

    For every detected value it searches the text for its whole-word
    occurrences and adds a detection for each one not already covered, carrying
    the source detection's label and confidence. Matching is case-insensitive by
    default, so a detected Patrick also catches a missed patrick, at the cost of
    false positives on common words. Set case_sensitive to trade recall for
    precision.

    Attributes:
        case_sensitive: Whether matching respects case.
    """

    def __init__(self, case_sensitive: bool = False) -> None:
        """Store whether matching respects case."""
        self.case_sensitive = case_sensitive

    def expand(self, text: str, detections: list[Detection]) -> list[Detection]:
        """Return the detections plus any missed whole-word occurrences."""
        expanded = list(detections)
        seen = {detection.span for detection in detections}
        flags = re.NOFLAG if self.case_sensitive else re.IGNORECASE

        for detection in detections:
            for span in find_all_word_boundary(text, detection.text, flags):
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
