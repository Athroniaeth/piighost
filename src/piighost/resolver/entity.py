from collections import defaultdict
from typing import Protocol

from piighost.models import Detection, Entity
from piighost.similarity import AnySimilarityFn, jaro_winkler_similarity


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

    def resolve(self, entities: list[Entity]) -> list[Entity]:
        """Group conflicting entities, merge each group, sort by position.

        Template method: the skeleton (group then merge then sort) is
        fixed here and shared with every subclass. Only the grouping
        strategy (:meth:`_group`) and the pairwise predicate
        (:meth:`have_conflict`) vary.

        Args:
            entities: The full list of entities.

        Returns:
            One merged entity per group, sorted by earliest ``start_pos``.
        """
        return self._merge_and_sort(self._group(entities))

    def have_conflict(self, entity_a: Entity, entity_b: Entity) -> bool:
        """Whether two entities share at least one common detection.

        The per-pair predicate consumed by :meth:`_group`. Subclasses
        override it to change what "conflict" means (see
        :class:`FuzzyEntityConflictResolver`).
        """
        detections_a = set(entity_a.detections)
        return any(d in detections_a for d in entity_b.detections)

    def _group(self, entities: list[Entity]) -> list[list[Entity]]:
        """Partition entities into connected components under ``have_conflict``.

        Uses union-find with path compression over entity indices, which
        computes the transitive closure of pairwise ``have_conflict``.
        That is only correct when the conflict relation is union-stable
        (merging two entities never removes a conflict they had
        individually), which holds for shared detections. A subclass
        whose ``have_conflict`` is not union-stable (e.g. text
        similarity) must override ``_group``; see
        :class:`FuzzyEntityConflictResolver`.
        """
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

        groups: dict[int, list[Entity]] = defaultdict(list)
        for i, entity in enumerate(entities):
            groups[find(i)].append(entity)
        return list(groups.values())

    @staticmethod
    def _merge(group: list[Entity]) -> Entity:
        """Fuse a group of entities into one, deduplicating detections.

        First-seen order is preserved: ``dict.fromkeys`` over the
        hashable frozen ``Detection`` dataclass keeps the first
        occurrence and drops later duplicates.
        """
        detections: list[Detection] = [d for e in group for d in e.detections]
        return Entity(detections=tuple(dict.fromkeys(detections)))

    @classmethod
    def _merge_and_sort(cls, groups: list[list[Entity]]) -> list[Entity]:
        """Merge each group, then sort the results by earliest ``start_pos``."""
        merged = [cls._merge(group) for group in groups]
        merged.sort(key=lambda e: min(d.position.start_pos for d in e.detections))
        return merged


class FuzzyEntityConflictResolver(MergeEntityConflictResolver):
    """Resolver that merges entities with similar canonical text.

    Subclasses ``MergeEntityConflictResolver`` and overrides
    ``have_conflict`` (string similarity instead of shared detections)
    and ``_group``: similarity is not transitive, so the base union-find
    (transitive closure over pairwise conflicts) would let chains of
    pairwise-similar texts over-merge distinct PIIs into a single
    placeholder.  Instead this resolver uses greedy anchor clustering,
    where each entity is only compared against the first entity of each
    existing group.  ``resolve``, ``_merge`` and the final sort are
    inherited unchanged.

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

    def _group(self, entities: list[Entity]) -> list[list[Entity]]:
        """Greedy anchor clustering on canonical similarity.

        Overrides the union-find grouping because similarity is not
        transitive: the transitive closure would let chains of
        pairwise-similar texts collapse distinct PIIs into one group.
        Each entity joins the first existing group whose *anchor* (its
        first entity) it conflicts with, otherwise it starts a new group.
        Merging and sorting are then inherited from the base.
        """
        groups: list[list[Entity]] = []
        for entity in entities:
            for group in groups:
                if self.have_conflict(group[0], entity):
                    group.append(entity)
                    break
            else:
                groups.append([entity])
        return groups
