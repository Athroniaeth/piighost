from typing import TYPE_CHECKING, Protocol

from piighost.models import Detection, Entity
from piighost.similarity import AnySimilarityFn, jaro_winkler_similarity

if TYPE_CHECKING:
    from piighost.config.models.entity_resolver import (
        DisabledEntityResolverConfig,
        FuzzyEntityResolverConfig,
        MergeEntityResolverConfig,
    )


class AnyEntityConflictResolver(Protocol):
    """Protocol defining the interface for entity conflict resolvers.

    When multiple entities share common detections (e.g. from different
    linker strategies), a resolver decides how to reconcile them.

    How a resolver decides that two entities conflict is an
    implementation detail of ``resolve``; it is not part of this
    protocol.
    """

    def resolve(self, entities: list[Entity]) -> list[Entity]:
        """Resolve conflicts across all entities.

        Args:
            entities: The full list of entities, potentially with
                shared detections.

        Returns:
            A list of entities with all conflicts resolved.
        """
        ...


class DisabledEntityConflictResolver:
    """Passthrough resolver that disables entity conflict resolution.

    Returns the input list of entities unchanged. Useful when entities
    are already known to be disjoint, or when the user explicitly wants
    to keep duplicates produced by separate linkers without merging them.

    Example:
        >>> from piighost.models import Detection, Entity, Span
        >>> e1 = Entity(detections=(Detection(text="Patrick", label="PERSON", position=Span(0, 7), confidence=0.9),))
        >>> e2 = Entity(detections=(Detection(text="Patrick", label="PERSON", position=Span(0, 7), confidence=0.5),))
        >>> resolver = DisabledEntityConflictResolver()
        >>> resolver.resolve([e1, e2]) == [e1, e2]
        True
    """

    @classmethod
    def from_config(
        cls, cfg: "DisabledEntityResolverConfig"
    ) -> "DisabledEntityConflictResolver":
        """Build a ``DisabledEntityConflictResolver`` from its validated configuration."""
        return cls()

    def resolve(self, entities: list[Entity]) -> list[Entity]:
        return list(entities)


class MergeEntityConflictResolver:
    """Resolver that merges entities sharing common detections.

    When two entities share at least one detection, they are merged
    into a single entity containing all their detections (deduplicated).
    This is transitive: if A shares a detection with B, and B shares
    one with C, all three are merged into one entity.

    Example:
        >>> from piighost.models import Detection, Entity, Span
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

    @classmethod
    def from_config(
        cls, cfg: "MergeEntityResolverConfig"
    ) -> "MergeEntityConflictResolver":
        """Build a ``MergeEntityConflictResolver`` from its validated configuration."""
        return cls()

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
        """Merge all entities that share common detections, transitively.

        Uses union-find with path compression over entity indices:
        every conflicting pair is unioned, then each root's detections
        are concatenated (deduplicated, input order preserved).

        Note:
            This computes the transitive closure of pairwise
            ``have_conflict``.  That is only correct when the conflict
            relation is union-stable (merging two entities never
            removes a conflict they had individually), which holds for
            shared detections.  Subclasses whose ``have_conflict`` is
            not union-stable (e.g. text similarity) must override
            ``resolve``, see ``FuzzyEntityConflictResolver``.

        Args:
            entities: The full list of entities.

        Returns:
            A merged list of entities with no shared detections,
            sorted by earliest ``start_pos``.
        """
        if not entities:
            return []

        parent = list(range(len(entities)))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for i in range(len(entities)):
            for j in range(i + 1, len(entities)):
                if find(i) != find(j) and self.have_conflict(entities[i], entities[j]):
                    parent[find(j)] = find(i)

        merged: dict[int, list[Detection]] = {}
        seen: dict[int, set[Detection]] = {}
        for i, entity in enumerate(entities):
            root = find(i)
            bucket = merged.setdefault(root, [])
            known = seen.setdefault(root, set())
            for d in entity.detections:
                if d not in known:
                    known.add(d)
                    bucket.append(d)

        result = [Entity(detections=tuple(dets)) for dets in merged.values()]
        result.sort(key=lambda e: min(d.position.start_pos for d in e.detections))
        return result


class FuzzyEntityConflictResolver(MergeEntityConflictResolver):
    """Resolver that merges entities with similar canonical text.

    Subclasses ``MergeEntityConflictResolver`` and overrides
    ``have_conflict`` to use string similarity instead of shared
    detections.  ``resolve`` is also overridden: similarity is not
    transitive, so the base union-find (transitive closure over
    pairwise conflicts) would let chains of pairwise-similar texts
    over-merge distinct PIIs into a single placeholder.  Instead this
    resolver uses greedy anchor clustering, where each entity is only
    compared against the first entity of each existing group.

    Args:
        similarity_fn: A ``(str, str) -> float`` function returning
            a score in [0.0, 1.0].  Defaults to Jaro-Winkler.
        threshold: Minimum similarity score to consider two entities
            as the same.  Defaults to 0.85.

    Example:
        >>> from piighost.models import Detection, Entity, Span
        >>> e1 = Entity(detections=(Detection("Patrick", "PERSON", Span(0, 7), 0.9),))
        >>> e2 = Entity(detections=(Detection("patric", "PERSON", Span(20, 26), 0.8),))
        >>> resolver = FuzzyEntityConflictResolver()
        >>> result = resolver.resolve([e1, e2])
        >>> len(result)
        1
    """

    _similarity_fn: AnySimilarityFn
    _threshold: float

    @classmethod
    def from_config(
        cls, cfg: "FuzzyEntityResolverConfig"
    ) -> "FuzzyEntityConflictResolver":
        """Build a ``FuzzyEntityConflictResolver`` from its validated configuration."""
        return cls(threshold=cfg.threshold)

    @property
    def threshold(self) -> float:
        """The minimum similarity score to consider two entities as the same."""
        return self._threshold

    def __init__(
        self,
        similarity_fn: AnySimilarityFn = jaro_winkler_similarity,
        threshold: float = 0.85,
    ) -> None:
        self._similarity_fn = similarity_fn
        self._threshold = threshold

    def have_conflict(self, entity_a: Entity, entity_b: Entity) -> bool:
        """Check whether two entities have similar canonical text.

        Args:
            entity_a: The first entity.
            entity_b: The second entity.

        Returns:
            ``True`` if the entities have the same label and their
            canonical texts are similar above the threshold.
        """
        if entity_a.label != entity_b.label:
            return False
        text_a = entity_a.canonical
        text_b = entity_b.canonical
        return self._similarity_fn(text_a, text_b) >= self._threshold

    def resolve(self, entities: list[Entity]) -> list[Entity]:
        """Group entities by greedy anchor clustering on canonical similarity.

        Entities are scanned in input order.  Each entity joins the first
        existing group whose *anchor* (the group's first entity) it is
        similar to, otherwise it starts a new group.  Comparing against
        the anchor only, not against every member, prevents chains of
        pairwise-similar texts from collapsing distinct PIIs into one
        placeholder (similarity is not transitive).  This preserves the
        grouping behaviour of the pre-union-find implementation.

        Args:
            entities: The full list of entities.

        Returns:
            Grouped entities, sorted by earliest ``start_pos``.
        """
        if not entities:
            return []

        anchors: list[Entity] = []
        buckets: list[list[Detection]] = []
        seen: list[set[Detection]] = []

        for entity in entities:
            for idx, anchor in enumerate(anchors):
                if self.have_conflict(anchor, entity):
                    for d in entity.detections:
                        if d not in seen[idx]:
                            seen[idx].add(d)
                            buckets[idx].append(d)
                    break
            else:
                anchors.append(entity)
                buckets.append(list(entity.detections))
                seen.append(set(entity.detections))

        result = [Entity(detections=tuple(dets)) for dets in buckets]
        result.sort(key=lambda e: min(d.position.start_pos for d in e.detections))
        return result
