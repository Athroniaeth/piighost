"""Shared test fixtures and fakes for the PIIGhost test suite."""

from typing import Sequence

from piighost.anonymizer.models import Entity


class FakeDetector:
    """Deterministic detector that returns pre-configured entities.

    Args:
        entities: The entities to return for every call to ``detect``.
    """

    def __init__(self, entities: list[Entity]) -> None:
        self._entities = entities

    def detect(
        self, text: str, active_labels: Sequence[str] | None = None
    ) -> list[Entity]:
        """Return pre-configured entities regardless of input."""
        return self._entities
