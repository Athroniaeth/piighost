"""Merge entity resolver: unite each group of entities that share a detection."""

from piighost.components.entity_resolver.base import BaseEntityResolver
from piighost.models import Entity


class MergeEntityResolver(BaseEntityResolver):
    """Merge each group of entities sharing a detection into one.

    When entities share a detection they are one value split across passes, so
    combining them is the natural fix: A-B-C and C-D share C and become
    A-B-C-D, its detections deduplicated in the order they arrived.

    The order is never rebuilt from positions. In a thread, each detection's
    span is an offset inside its own message, so positions from two messages
    cannot be compared, and an entity takes the label of its first detection: a
    sort by position would let a later message relabel a value whose token the
    model already holds.
    """

    def _reduce(self, conflicting: list[Entity]) -> list[Entity]:
        """Combine the group into a single entity, first detections first."""
        detections = (d for entity in conflicting for d in entity.detections)
        return [Entity(tuple(dict.fromkeys(detections)))]
