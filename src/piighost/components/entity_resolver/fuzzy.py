"""Fuzzy entity resolver: merge near-duplicate values (optional: fuzzy).

Typos and OCR damage split one value into several entities the exact linker
cannot group, such as Patrick and Patrik, so they would each get their own
placeholder. This resolver merges same-label entities whose texts are nearly
identical, scored by rapidfuzz. The module needs the rapidfuzz package; it is
guarded so importing it without the dependency raises an ImportError pointing
at the extra.
"""

import importlib.util
from collections.abc import Callable

from piighost.components.entity_resolver.merge import MergeEntityResolver
from piighost.models import Entity

if importlib.util.find_spec("rapidfuzz") is None:
    raise ImportError(
        "FuzzyEntityResolver requires the rapidfuzz package. "
        "Install it with: pip install piighost[fuzzy]"
    )

from rapidfuzz.distance import JaroWinkler

_DEFAULT_THRESHOLD = 0.85
"""Minimum similarity for two values to read as one, on a 0 to 1 scale.

The Jaro-Winkler default that keeps one-letter typos of a short name together
without collapsing genuinely distinct names.
"""


class FuzzyEntityResolver(MergeEntityResolver):
    """Merge same-label entities whose values are nearly identical.

    Two entities read as one value when they share a label and their casefolded
    texts score at or above the threshold, by Jaro-Winkler unless another
    similarity is injected. The merge itself is inherited: a group combines into
    one entity, its detections deduplicated and position-ordered.

    Similarity is not transitive, so the clustering deviates from the base
    template's transitive closure: each entity is compared against the first
    member of each existing group, the anchor, and joins the first group whose
    anchor it matches. A chain of pairwise-similar texts therefore cannot drift
    distinct values into a single placeholder.

    Attributes:
        threshold: The minimum similarity score for two values to merge.
    """

    def __init__(
        self,
        threshold: float = _DEFAULT_THRESHOLD,
        similarity: Callable[[str, str], float] | None = None,
    ) -> None:
        """Store the threshold and the similarity, Jaro-Winkler by default."""
        self.threshold = threshold
        self._similarity = similarity or JaroWinkler.normalized_similarity

    def _conflict_groups(self, entities: list[Entity]) -> list[list[Entity]]:
        """Cluster each entity onto the first group whose anchor it matches."""
        groups: list[list[Entity]] = []

        for entity in entities:
            group = self._anchored_group(groups, entity)
            if group is None:
                groups.append([entity])
            else:
                group.append(entity)
        return groups

    def _anchored_group(
        self, groups: list[list[Entity]], entity: Entity
    ) -> list[Entity] | None:
        """Return the first group whose anchor reads as the entity's value."""
        for group in groups:
            anchor = group[0]
            if self._same_value(entity, anchor):
                return group
        return None

    def _same_value(self, first: Entity, second: Entity) -> bool:
        """Whether two entities read as one value: one label, similar texts."""
        if first.label != second.label:
            return False
        score = self._similarity(first.text.casefold(), second.text.casefold())
        return score >= self.threshold
