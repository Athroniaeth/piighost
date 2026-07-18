"""Merge entity resolver: unite each group of entities that share a detection."""

from piighost.entity_resolver.base import BaseEntityResolver
from piighost.models import Entity


class MergeEntityResolver(BaseEntityResolver):
    """Merge each group of entities sharing a detection into one.

    When entities share a detection they are one value split across passes, so
    combining them is the natural fix: A-B-C and C-D share C and become
    A-B-C-D, its detections deduplicated and ordered by position.
    """

    def _reduce(self, conflicting: list[Entity]) -> list[Entity]:
        """Combine the group into a single entity."""
        uniq = {detection for entity in conflicting for detection in entity.detections}
        # a set has no order, so sort the detections back into position order
        detections = tuple(sorted(uniq))
        return [Entity(detections)]
