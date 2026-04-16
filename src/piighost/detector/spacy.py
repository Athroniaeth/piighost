import importlib.util

from piighost.detector.base import BaseNERDetector
from piighost.models import Detection, Span

if importlib.util.find_spec("spacy") is None:
    raise ImportError(
        "You must install spacy to use SpacyDetector, please install piighost[spacy]"
    )

import spacy


class SpacyDetector(BaseNERDetector):
    """Detect entities using a spaCy NER model.

    Wraps a loaded spaCy ``Language`` model so that callers can inject a
    pre-loaded model (useful for tests and shared workers).

    Args:
        model: A loaded spaCy ``Language`` model instance.
        labels: Entity types to keep. ``None`` or ``[]`` keeps every entity
            spaCy produces (no filtering, label is passed through).
            A list performs identity mapping and filters by those labels.
            A ``{external: internal}`` dict filters by internal labels and
            rewrites :class:`Detection.label` to the corresponding external.

    Example:
        >>> import spacy
        >>> nlp = spacy.load("fr_core_news_sm")
        >>> detector = SpacyDetector(model=nlp, labels=["PER", "LOC"])
        >>> # Remap spaCy's "PER"/"LOC" to stable external labels:
        >>> detector = SpacyDetector(
        ...     model=nlp,
        ...     labels={"PERSON": "PER", "LOCATION": "LOC"},
        ... )
        >>> detections = await detector.detect("Patrick habite à Paris")
    """

    def __init__(
        self,
        model: spacy.language.Language,
        labels: list[str] | dict[str, str] | None = None,
    ) -> None:
        super().__init__(labels)
        self.model = model

    async def detect(self, text: str) -> list[Detection]:
        """Run spaCy NER and convert results to ``Detection`` objects.

        Args:
            text: The input text to search for entities.

        Returns:
            Detections for each entity found by the model. When the label
            map is empty, every entity is kept with its spaCy label. When
            the map is non-empty, only entities whose spaCy label is a
            mapped internal label are kept, and the external label is used
            in :class:`Detection.label`.
        """
        doc = self.model(text)
        detections: list[Detection] = []

        for ent in doc.ents:
            if not self._label_map:
                label = ent.label_
            else:
                mapped = self._map_label(ent.label_)
                if mapped is None:
                    continue
                label = mapped

            detections.append(
                Detection(
                    text=ent.text,
                    label=label,
                    position=Span(start_pos=ent.start_char, end_pos=ent.end_char),
                    confidence=1.0,
                )
            )

        return detections
