"""Exact-match detector: finds configured literal values, mainly for tests."""

import re

from piighost.models import Detection, Span


class ExactMatchDetector:
    """Detector that finds occurrences of configured literal values.

    It scans the text for each configured value and emits one detection per
    occurrence, with confidence 1.0. It carries no model, so it is cheap and
    needs no optional dependency, which makes it the detector of choice for
    exercising the pipeline in tests.

    Attributes:
        values: Mapping of literal value to the PII label to emit for it.
    """

    def __init__(self, values: dict[str, str]) -> None:
        """Store the mapping of literal value to PII label."""
        self.values = values

    async def detect(self, text: str) -> list[Detection]:
        """Return one detection per occurrence of each configured value."""
        detections: list[Detection] = []
        for value, label in self.values.items():
            # re.finditer yields every non-overlapping match with its offsets;
            # re.escape keeps value literal so regex metacharacters do not apply.
            needle = re.escape(value)

            for match in re.finditer(needle, text):
                start = match.start()
                end = match.end()

                span = Span(start, end)
                detection = Detection(
                    span=span,
                    text=value,
                    label=label,
                    confidence=1.0,
                )
                detections.append(detection)
        return detections
