"""Exact-match detector: finds configured literal values, mainly for tests."""

import re

from piighost.models import Detection
from piighost.text import find_all_word_boundary


class ExactMatchDetector:
    """Detector that finds occurrences of configured literal values.

    It scans the text for each configured value and emits one detection per
    whole-word occurrence, with confidence 1.0. Matching is on word boundaries,
    so a value does not fire inside a longer word (no "Ann" inside "Anne"), and
    case-insensitive by default, so a value matches whatever its casing while the
    detection keeps the text as it appears. It carries no model, so it is cheap
    and needs no optional dependency, which makes it the detector of choice for
    exercising the pipeline in tests.

    Attributes:
        values: Mapping of literal value to the PII label to emit for it.
        case_sensitive: Whether matching respects case. False by default.
    """

    def __init__(self, values: dict[str, str], case_sensitive: bool = False) -> None:
        """Store the value-to-label mapping and the case-sensitivity policy."""
        self.values = values
        self.case_sensitive = case_sensitive

    async def detect(self, text: str) -> list[Detection]:
        """Return one detection per whole-word occurrence of each value."""
        flags = re.NOFLAG if self.case_sensitive else re.IGNORECASE
        detections: list[Detection] = []
        for value, label in self.values.items():
            for span in find_all_word_boundary(text, value, flags):
                # Keep the matched text as it appears, which may differ in case
                # from the configured value, so replacement stays exact.
                detection = Detection(
                    span=span,
                    text=span.extract(text),
                    label=label,
                    confidence=1.0,
                )
                detections.append(detection)
        return detections
