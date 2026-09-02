"""Redact placeholder factory: one constant token for every entity."""

from piighost.components.placeholder.base import (
    AnyPlaceholderFactory,
    BaseDelimitedPlaceholderFactory,
)
from piighost.components.placeholder.streaming import LABEL_INNER
from piighost.components.placeholder.tags import PreservesNothing
from piighost.models import Entity


class RedactPlaceholderFactory(
    BaseDelimitedPlaceholderFactory, AnyPlaceholderFactory[PreservesNothing]
):
    """Map every entity to the same constant token.

    Each entity collapses to one token, such as <<REDACT>>, so a reader learns
    that something was removed but nothing about its type, count, or relations.
    The mapping cannot be reversed, which is why the tag is PreservesNothing.
    """

    _inner_pattern: str = LABEL_INNER
    """The constant token is a bare label, with no colon-separated identifier."""

    def create(self, entities: list[Entity]) -> dict[Entity, PreservesNothing]:
        """Return the constant redaction token for every entity."""
        token = PreservesNothing(self._wrap("REDACT"))
        return {entity: token for entity in entities}
