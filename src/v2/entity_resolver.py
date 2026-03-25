from collections import defaultdict
from typing import Protocol

from v2.models import Detection, Entity


class AnyEntityConflictResolver(Protocol):
    """Protocol defining the interface for entity conflict resolvers.

    When multiple entities share common detections (e.g. from different
    linker strategies), a resolver decides how to reconcile them.
    """

    def have_conflict(self, entity_a: Entity, entity_b: Entity) -> bool:
        """Check whether two entities are in conflict.

        Args:
            entity_a: The first entity.
            entity_b: The second entity.

        Returns:
            ``True`` if the two entities share at least one detection.
        """
        ...

    def resolve(self, entities: list[Entity]) -> list[Entity]:
        """Resolve conflicts across all entities.

        Args:
            entities: The full list of entities, potentially with
                shared detections.

        Returns:
            A list of entities with all conflicts resolved.
        """
        ...


class MergeEntityConflictResolver:
    """Resolver that merges entities sharing common detections.

    When two entities share at least one detection, they are merged
    into a single entity containing all their detections (deduplicated).
    This is transitive: if A shares a detection with B, and B shares
    one with C, all three are merged into one entity.

    Example:
        >>> from v2.models import Detection, Entity, Span
        >>> d_a = Detection(text="Patrick", label="PERSON", position=Span(0, 7), confidence=0.9)
        >>> d_b = Detection(text="Patrick", label="PERSON", position=Span(20, 27), confidence=0.9)
        >>> d_c = Detection(text="patric", label="PERSON", position=Span(30, 36), confidence=0.8)
        >>> entity_1 = Entity(detections=[d_a, d_b])
        >>> entity_2 = Entity(detections=[d_b, d_c])
        >>> resolver = MergeEntityConflictResolver()
        >>> result = resolver.resolve([entity_1, entity_2])
        >>> len(result)
        1
        >>> len(result[0].detections)
        3
    """

    def have_conflict(self, entity_a: Entity, entity_b: Entity) -> bool:
        """Check whether two entities share at least one common detection.

        Args:
            entity_a: The first entity.
            entity_b: The second entity.

        Returns:
            ``True`` if the entities have at least one detection in common.
        """
        detections_a = set(entity_a.detections)
        return any(d in detections_a for d in entity_b.detections)

    def resolve(self, entities: list[Entity]) -> list[Entity]:
        """Merge all entities that share common detections transitively.

        Uses a Union-Find algorithm to efficiently group entities that
        are connected through shared detections.

        Args:
            entities: The full list of entities.

        Returns:
            A merged list of entities with no shared detections,
            sorted by earliest ``start_pos``.
        """
        if not entities:
            return []

        n = len(entities)
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: int, y: int) -> None:
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        for i in range(n):
            for j in range(i + 1, n):
                if self.have_conflict(entities[i], entities[j]):
                    union(i, j)

        groups: dict[int, list[int]] = defaultdict(list)
        for i in range(n):
            groups[find(i)].append(i)

        result: list[Entity] = []
        for indices in groups.values():
            seen: set[Detection] = set()
            merged_detections: list[Detection] = []
            for idx in indices:
                for d in entities[idx].detections:
                    if d not in seen:
                        seen.add(d)
                        merged_detections.append(d)
            entity = Entity(detections=merged_detections)
            result.append(entity)

        result.sort(key=lambda e: min(d.position.start_pos for d in e.detections))
        return result
