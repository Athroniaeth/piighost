"""spaCy detector (optional: spacy).

Wraps a spaCy Language model so a caller injects a loaded instance or passes a
model name to load. This module needs the spacy package; it is guarded so
importing it without the dependency raises an ImportError pointing at the extra.
"""

import importlib.util

from piighost.components.detector.ner.base import BaseNERDetector
from piighost.models import Detection, Span

if importlib.util.find_spec("spacy") is None:
    raise ImportError(
        "SpacyDetector requires the spacy package. "
        "Install it with: pip install piighost[spacy]"
    )

import spacy  # pyrefly: ignore[missing-import]
from spacy.language import Language  # pyrefly: ignore[missing-import]


class SpacyDetector(BaseNERDetector):
    """Detect PII with a spaCy NER model.

    labels is optional. When omitted, every entity spaCy produces is kept with
    its spaCy label. A str model is loaded with spacy.load; a loaded instance is
    used as-is.

    Attributes:
        model: The loaded spaCy Language model run over each text.
    """

    def __init__(
        self,
        model: Language | str,
        labels: list[str] | dict[str, str] | None = None,
        max_concurrency: int | None = None,
    ) -> None:
        """Store or load the model, then set the labels."""
        super().__init__(labels, max_concurrency=max_concurrency)
        self.model = spacy.load(model) if isinstance(model, str) else model

    async def _raw_detect(self, text: str) -> list[Detection]:
        """Run spaCy and build one detection per entity, native labels kept."""
        doc = await self._run_blocking(self.model, text)
        detections: list[Detection] = []
        for entity in doc.ents:
            span = Span(entity.start_char, entity.end_char)
            detection = Detection(
                span=span,
                text=entity.text,
                label=entity.label_,
                confidence=1.0,
            )
            detections.append(detection)
        return detections
