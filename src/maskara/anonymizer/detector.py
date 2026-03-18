"""Entity detection abstraction and GLiNER2 implementation."""

from dataclasses import dataclass
from typing import Protocol, Sequence

from gliner2 import GLiNER2

from maskara.anonymizer.models import Entity


class EntityDetector(Protocol):
    """Interface for named-entity detection (dependency-injection point).

    Implementations may wrap any NER backend: GLiNER, spaCy, a remote
    API, etc.  The anonymiser depends only on this protocol.
    """

    def detect(self, text: str, labels: Sequence[str]) -> list[Entity]:
        """Detect entities in *text* for the requested *labels*.

        Args:
            text: The source string to analyse.
            labels: Entity types to look for (e.g. ``["PERSON", "LOCATION"]``).

        Returns:
            A list of detected entities (may contain duplicates across
            positions but not at the exact same span).
        """
        ...  # pragma: no cover


@dataclass
class GlinerDetector:
    """Detect entities using a GLiNER2 model.

    The class lazily wraps a ``GLiNER`` model instance so that callers
    can inject a pre-loaded model (useful for tests and shared workers).

    Args:
        model: A loaded ``GLiNER`` model instance.
        threshold: Minimum confidence score to keep a prediction.
        flat_ner: Whether to use flat NER mode (no nested entities).

    Example:
        >>> from gliner import GLiNER
        >>> model = GLiNER.from_pretrained("urchade/gliner_multi_pii-v1")
        >>> detector = GlinerDetector(model=model, threshold=0.5)
        >>> entities = detector.detect("Je m'appelle Patrick", ["PERSON"])
    """

    model: GLiNER2
    threshold: float = 0.5
    flat_ner: bool = True

    def detect(self, text: str, labels: Sequence[str]) -> list[Entity]:
        """Run GLiNER prediction and convert results to ``Entity`` objects.

        Args:
            text: The source string.
            labels: Entity types to search for.

        Returns:
            Entities whose score meets the configured threshold.
        """
        raw_entities = self.model.extract_entities(
            text,
            entity_types=list(labels),
            threshold=self.threshold,
            include_spans=True,
            include_confidence=True,
        )["entities"]

        return [
            Entity(
                text=entity["text"],
                label=entity_type,
                start=entity["start"],
                end=entity["end"],
                score=entity["confidence"],
            )
            for entity_type, list_entity in raw_entities.items()
            for entity in list_entity
        ]
