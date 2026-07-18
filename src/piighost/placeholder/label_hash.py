"""Label hash placeholder factory: <<LABEL:hash>> with an opaque counter suffix."""

import hashlib
from collections import defaultdict

from piighost.models import Entity
from piighost.placeholder.base import AnyPlaceholderFactory
from piighost.placeholder.tags import PreservesLabeledIdentityOpaque


class LabelHashPlaceholderFactory(
    AnyPlaceholderFactory[PreservesLabeledIdentityOpaque]
):
    """Number each entity within its label, then render that count as a hash.

    Like the counter factory it numbers entities per label in order, but it
    shows the number as a short hash, so <<PERSON:1>> reads as <<PERSON:6b86b273>>.
    The hash is only for the opaque look: it digests the label and the ordinal,
    never the value, so the token carries nothing about the PII and consecutive
    entities look unrelated. It is trivially reversible, which does not matter
    since the input is only an ordinal. Distinct entities still get distinct
    tokens, hence the tag PreservesLabeledIdentityOpaque.

    Attributes:
        hash_length: How many hex characters of each digest to keep.
    """

    def __init__(self, hash_length: int = 8) -> None:
        """Store how many hex characters of each digest to keep."""
        self.hash_length = hash_length

    def create(
        self, entities: list[Entity]
    ) -> dict[Entity, PreservesLabeledIdentityOpaque]:
        """Return an opaque per-label numbered token for every entity."""
        counters: dict[str, int] = defaultdict(int)
        tokens: dict[Entity, PreservesLabeledIdentityOpaque] = {}

        for entity in entities:
            counters[entity.label] += 1
            tokens[entity] = self._token(entity.label, counters[entity.label])

        return tokens

    def _token(self, label: str, number: int) -> PreservesLabeledIdentityOpaque:
        """Render a label and its ordinal as the <<LABEL:hash>> token."""
        digest = hashlib.sha256(f"{label}:{number}".encode()).hexdigest()
        return PreservesLabeledIdentityOpaque(f"<<{label}:{digest[: self.hash_length]}>>")
