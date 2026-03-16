"""Entity extraction: Protocol for DI and GLiNER2 adapter."""

from typing import Protocol

from gliner2 import GLiNER2

from maskara.anonymizer.models import DetectedEntity


class EntityExtractor(Protocol):
    """Interface for entity extraction (dependency-injection point).

    Any backend (GLiNER2, spaCy, regex, mock) can implement this.
    """

    def extract(self, text: str, labels: list[str]) -> list[DetectedEntity]:
        """Detect named entities in *text*.

        Args:
            text: The source string to analyse.
            labels: Entity types to look for (e.g. ``["person", "location"]``).

        Returns:
            Detected entities with their spans and confidence.
        """
        ...  # pragma: no cover


class GlinerExtractor:
    """Adapter around a ``GLiNER2`` model.

    Args:
        model: A loaded ``GLiNER2`` instance.
        min_confidence: Discard detections below this threshold.
    """

    model: GLiNER2
    min_confidence: float

    def __init__(self, model: object, min_confidence: float = 0.5) -> None:
        self._model = model
        self._min_confidence = min_confidence

    def extract(self, text: str, labels: list[str]) -> list[DetectedEntity]:
        """Run GLiNER2 and return high-confidence detections.

        Args:
            text: The source string to analyse.
            labels: Entity types to look for.

        Returns:
            Filtered detections above ``min_confidence``.
        """
        results: list[DetectedEntity] = []
        raw = self._model.extract_entities(  # type: ignore[attr-defined]
            text,
            labels,
            include_spans=True,
            include_confidence=True,
            threshold=self._min_confidence,
        )

        for label, entities in raw["entities"].items():
            for entity in entities:
                confidence = entity["confidence"]

                results.append(
                    DetectedEntity(
                        text=entity["text"],
                        label=label,
                        start=entity["span"][0],
                        end=entity["span"][1],
                        confidence=confidence,
                    )
                )
        return results
