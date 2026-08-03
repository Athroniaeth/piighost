"""Word-boundary detection expander: find missed whole-word occurrences."""

import re
from collections.abc import Iterable

from piighost.components.expander.base import BaseDetectionExpander
from piighost.models import Detection, Span
from piighost.text import find_all_word_boundary


class WordBoundaryExpander(BaseDetectionExpander):
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

    def _find_occurrences(self, text: str, detection: Detection) -> Iterable[Span]:
        """Return the whole-word spans of the detection's value in the text."""
        flags = re.NOFLAG if self.case_sensitive else re.IGNORECASE
        return find_all_word_boundary(text, detection.text, flags)
