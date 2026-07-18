"""Redact placeholder factory: one constant token for every entity."""

from piighost.models import Entity
from piighost.placeholder.base import AnyPlaceholderFactory
from piighost.placeholder.tags import PreservesNothing

REDACT_TOKEN = PreservesNothing("[REDACT]")
"""The constant token every entity collapses to, tagged as preserving nothing."""


class RedactPlaceholderFactory(AnyPlaceholderFactory[PreservesNothing]):
    """Map every entity to the same constant token.

    Each entity collapses to REDACT_TOKEN, so a reader learns that something was
    removed but nothing about its type, count, or relations. The mapping cannot
    be reversed, which is why the tag is PreservesNothing.
    """

    def create(self, entities: list[Entity]) -> dict[Entity, PreservesNothing]:
        """Return the constant redaction token for every entity."""
        return {entity: REDACT_TOKEN for entity in entities}
