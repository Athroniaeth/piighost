"""Separate entity resolver: give each shared detection to a single entity."""

from piighost.components.entity_resolver.base import BaseEntityResolver
from piighost.models import Detection, Entity, Span


class SeparateEntityResolver(BaseEntityResolver):
    """Keep conflicting entities apart, giving each shared detection to the largest.

    Where MergeEntityResolver unites a conflict group, this one separates it: a
    detection held by several entities goes to the largest of them and is dropped
    from the rest. Size is the entity's detection count; a tie goes to the entity
    whose earliest occurrence comes first in the text. An entity left with no
    detection is discarded. So A-B-C and C-D, sharing C, become A-B-C and D.
    """

    def _reduce(self, conflicting: list[Entity]) -> list[Entity]:
        """Assign each detection to its largest holder, dropping emptied entities."""

        def rank(entity: Entity) -> tuple[int, Span]:
            """Rank an entity: most detections first, earliest occurrence on a tie."""
            return -len(entity.detections), min(entity.spans)

        kept: list[list[Detection]] = [[] for _ in conflicting]

        for index, entity in enumerate(conflicting):
            for detection in entity.detections:
                holders = [
                    other for other in conflicting if detection in other.detections
                ]
                if min(holders, key=rank) is entity:
                    kept[index].append(detection)

        return [Entity(tuple(detections)) for detections in kept if detections]
