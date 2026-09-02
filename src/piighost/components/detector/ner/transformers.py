"""Transformers detector (optional: transformers).

Wraps a Hugging Face token-classification pipeline so a caller injects a built
pipeline or passes a model name to load. This module needs the transformers
package; it is guarded so importing it without the dependency raises an
ImportError pointing at the extra.
"""

import importlib.util

from piighost.components.detector.ner.base import BaseNERDetector
from piighost.models import Detection, Span

if importlib.util.find_spec("transformers") is None:
    raise ImportError(
        "TransformersDetector requires the transformers package. "
        "Install it with: pip install piighost[transformers]"
    )

from transformers.pipelines.token_classification import (  # pyrefly: ignore[missing-import]
    TokenClassificationPipeline,
)


class TransformersDetector(BaseNERDetector):
    """Detect PII with a Hugging Face token-classification pipeline.

    labels is optional. When omitted, every entity is kept with its model-native
    label. A str pipeline is loaded with the transformers pipeline factory as an
    ner pipeline; a built pipeline is used as-is. An entity scoring below
    threshold is dropped.

    Attributes:
        pipeline: The token-classification pipeline run over each text.
        threshold: The score below which a detected entity is dropped.
    """

    def __init__(
        self,
        pipeline: TokenClassificationPipeline | str,
        labels: list[str] | dict[str, str] | None = None,
        threshold: float = 0.0,
        max_concurrency: int | None = None,
        aggregation_strategy: str = "simple",
        max_chars: int | None = None,
        auto_chunk: bool = True,
    ) -> None:
        """Store or build the pipeline, then set the labels and threshold.

        A str pipeline is loaded with the given aggregation_strategy, so sub-word
        tokens are grouped into whole entities with a span and an aggregated
        score. The default, "simple", suits most NER models. It applies only when
        building from a name; a pipeline passed in keeps its own strategy.
        """
        super().__init__(
            labels,
            max_concurrency=max_concurrency,
            max_chars=max_chars,
            auto_chunk=auto_chunk,
        )
        if isinstance(pipeline, str):
            from transformers import (
                pipeline as hf_pipeline,  # pyrefly: ignore[missing-import, missing-module-attribute]
            )

            pipeline = hf_pipeline(
                "token-classification",
                model=pipeline,
                aggregation_strategy=aggregation_strategy,
            )
        self.pipeline = pipeline
        self.threshold = threshold

    async def _raw_detect(self, text: str) -> list[Detection]:
        """Run the pipeline and build detections, dropping sub-threshold ones."""
        results = await self._run_blocking(self.pipeline, text)
        detections: list[Detection] = []
        for entity in results:
            score = float(entity["score"])
            if score < self.threshold:
                continue
            native_label = entity.get("entity_group", entity.get("entity", "UNKNOWN"))
            start = int(entity["start"])
            end = int(entity["end"])
            span = Span(start, end)
            detection = Detection(
                span=span,
                text=text[start:end],
                label=native_label,
                confidence=score,
            )
            detections.append(detection)
        return detections
