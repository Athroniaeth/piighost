"""Regex detector: find PII by matching configured patterns, one per label."""

import re

from piighost.models import Detection, Span


class RegexDetector:
    """Detector that finds PII by matching regex patterns, one per label.

    Each pattern is compiled once at construction. detect emits one detection
    per non-overlapping match, at a flat confidence of 1.0. It carries no
    checksum validator and no optional dependency, so it stays cheap and matches
    on shape alone. A structured value mangled by OCR is kept rather than
    dropped, because dropping a real value would leak it.

    Attributes:
        patterns: Mapping of PII label to the regex pattern string to match.
    """

    def __init__(self, patterns: dict[str, str]) -> None:
        """Compile every configured pattern, keyed by its label."""
        self.patterns = patterns
        self._compiled: dict[str, re.Pattern[str]] = {
            label: re.compile(pattern) for label, pattern in patterns.items()
        }

    async def detect(self, text: str) -> list[Detection]:
        """Return one detection per non-overlapping match of each pattern."""
        detections: list[Detection] = []
        for label, compiled in self._compiled.items():
            for match in compiled.finditer(text):
                span = Span(match.start(), match.end())
                detection = Detection(
                    span=span,
                    text=match.group(),
                    label=label,
                    confidence=1.0,
                )
                detections.append(detection)
        return detections
