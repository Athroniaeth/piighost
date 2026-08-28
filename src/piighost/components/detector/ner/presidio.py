"""Presidio detector (optional: presidio).

Wraps a Presidio AnalyzerEngine so a caller reuses Presidio's recognizers inside
a piighost pipeline. This module needs the presidio-analyzer package; it is
guarded so importing it without the dependency raises an ImportError pointing at
the extra.
"""

import importlib.util

from piighost.components.detector.ner.base import BaseNERDetector
from piighost.models import Detection, Span

if importlib.util.find_spec("presidio_analyzer") is None:
    raise ImportError(
        "PresidioDetector requires the presidio-analyzer package. "
        "Install it with: pip install piighost[presidio]"
    )

from presidio_analyzer import (  # pyrefly: ignore[missing-import]
    AnalyzerEngine,
)


class PresidioDetector(BaseNERDetector):
    """Detect PII with a Presidio AnalyzerEngine.

    The analyzer is injected, because an AnalyzerEngine is assembled from an NLP
    engine and a recognizer registry rather than loaded from a single model
    name. Presidio returns an entity type, a span, and a score per finding,
    which the base class then maps and filters through the labels argument.

    Attributes:
        analyzer: The Presidio AnalyzerEngine queried for entities.
        language: The language code passed to analyze.
        threshold: The score at or above which Presidio keeps a finding.
    """

    def __init__(
        self,
        analyzer: AnalyzerEngine,
        labels: list[str] | dict[str, str] | None = None,
        language: str = "en",
        threshold: float = 0.0,
        max_concurrency: int | None = None,
    ) -> None:
        """Store the analyzer, then set the labels, language, and threshold."""
        super().__init__(labels, max_concurrency=max_concurrency)
        self.analyzer = analyzer
        self.language = language
        self.threshold = threshold

    async def _raw_detect(self, text: str) -> list[Detection]:
        """Run Presidio and build one detection per finding, native types kept."""
        results = await self._run_blocking(
            self.analyzer.analyze,
            text,
            language=self.language,
            entities=self.internal_labels or None,
            score_threshold=self.threshold,
        )
        detections: list[Detection] = []
        for result in results:
            span = Span(result.start, result.end)
            detection = Detection(
                span=span,
                text=text[result.start : result.end],
                label=result.entity_type,
                confidence=result.score,
            )
            detections.append(detection)
        return detections
