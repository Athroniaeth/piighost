"""GLiNER2 detector (optional: gliner2).

Wraps a GLiNER2 model so a caller injects a loaded instance or passes a model
name to load. This module needs the gliner2 package; it is guarded so importing
it without the dependency raises an ImportError pointing at the extra.
"""

import importlib.util

from piighost.components.detector.ner.base import BaseNERDetector
from piighost.models import Detection, Span

if importlib.util.find_spec("gliner2") is None:
    raise ImportError(
        "Gliner2Detector requires the gliner2 package. "
        "Install it with: pip install piighost[gliner2]"
    )

from gliner2 import GLiNER2  # pyrefly: ignore[missing-import]  # noqa: E402


class Gliner2Detector(BaseNERDetector):
    """Detect PII with a GLiNER2 model.

    labels is required, because GLiNER2 is queried with the internal labels. A
    str model is loaded with GLiNER2.from_pretrained; a loaded instance is used
    as-is.
    """

    def __init__(
        self,
        model: GLiNER2 | str,
        labels: list[str] | dict[str, str],
        threshold: float = 0.5,
        max_concurrency: int | None = None,
    ) -> None:
        """Store or load the model, then set the labels and threshold."""
        super().__init__(labels, max_concurrency=max_concurrency)
        self.model = GLiNER2.from_pretrained(model) if isinstance(model, str) else model
        self.threshold = threshold

    async def _raw_detect(self, text: str) -> list[Detection]:
        """Run GLiNER2 and build one detection per entity, native labels kept."""
        result = await self._run_blocking(
            self.model.extract_entities,
            text,
            self.internal_labels,
            threshold=self.threshold,
            include_spans=True,
            include_confidence=True,
        )
        detections: list[Detection] = []
        for native_label, entities in result["entities"].items():
            for entity in entities:
                span = Span(entity["start"], entity["end"])
                detections.append(
                    Detection(
                        span=span,
                        text=entity["text"],
                        label=native_label,
                        confidence=entity["confidence"],
                    )
                )
        return detections
