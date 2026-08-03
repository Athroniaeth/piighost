"""Label counter placeholder factory: <<LABEL:n>> tokens, unique per entity."""

from collections import defaultdict

from piighost.models import Entity
from piighost.components.placeholder.base import AnyPlaceholderFactory
from piighost.components.placeholder.tags import PreservesLabeledIdentityOpaque


class LabelCounterPlaceholderFactory(
    AnyPlaceholderFactory[PreservesLabeledIdentityOpaque]
):
    """Number each entity within its label, as <<LABEL:n>>.

    The first person becomes <<PERSON:1>>, the second <<PERSON:2>>, while an
    email starts its own count at <<EMAIL:1>>. Every entity gets a distinct token
    that also names its label, so the mapping reveals the type yet stays
    reversible, hence the tag PreservesLabeledIdentityOpaque. The count follows
    the entity order, so the same entity list always yields the same tokens.
    """

    def create(
        self, entities: list[Entity]
    ) -> dict[Entity, PreservesLabeledIdentityOpaque]:
        """Return a per-label numbered token for every entity."""
        counters: dict[str, int] = defaultdict(int)
        tokens: dict[Entity, PreservesLabeledIdentityOpaque] = {}

        for entity in entities:
            counters[entity.label] += 1
            token = f"<<{entity.label}:{counters[entity.label]}>>"
            tokens[entity] = PreservesLabeledIdentityOpaque(token)

        return tokens
