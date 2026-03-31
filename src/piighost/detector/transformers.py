import importlib.util

from piighost.models import Detection, Span

if importlib.util.find_spec("transformers") is None:
    raise ImportError(
        "You must install transformers to use TransformersDetector, "
        "please install piighost[transformers]"
    )

from transformers.pipelines.token_classification import TokenClassificationPipeline


class TransformersDetector:
    """Detect entities using a Hugging Face token-classification pipeline.

    Wraps a loaded ``TokenClassificationPipeline`` so that callers can
    inject a pre-built pipeline (useful for tests and shared workers).

    Args:
        pipeline: A loaded HF ``TokenClassificationPipeline``.
        labels: Entity types to keep (``None`` keeps all).

    Example:
        >>> from transformers import pipeline
        >>> ner = pipeline("ner", model="dslim/bert-base-NER", aggregation_strategy="simple")
        >>> detector = TransformersDetector(pipeline=ner, labels=["PER", "LOC"])
        >>> detections = await detector.detect("Patrick lives in Paris")
    """

    def __init__(
        self,
        pipeline: TokenClassificationPipeline,
        labels: list[str] | None = None,
    ) -> None:
        self.pipeline = pipeline
        self.labels = labels

    async def detect(self, text: str) -> list[Detection]:
        """Run HF token-classification and convert results to ``Detection`` objects.

        Args:
            text: The input text to search for entities.

        Returns:
            Detections for each entity found by the model.
        """
        results = self.pipeline(text)
        return [
            Detection(
                text=text[ent["start"] : ent["end"]],
                label=ent.get("entity_group", ent.get("entity", "UNKNOWN")),
                position=Span(start_pos=ent["start"], end_pos=ent["end"]),
                confidence=float(ent["score"]),
            )
            for ent in results
            if self.labels is None
            or ent.get("entity_group", ent.get("entity")) in self.labels
        ]
