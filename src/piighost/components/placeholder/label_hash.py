"""Label hash placeholder factory: <<LABEL:hash>> with an opaque counter suffix."""

import hashlib

from piighost.components.placeholder.base import BaseCounterPlaceholderFactory
from piighost.components.placeholder.streaming import DEFAULT_PREFIX, DEFAULT_SUFFIX
from piighost.components.placeholder.tags import PreservesLabeledIdentityOpaque


class LabelHashPlaceholderFactory(BaseCounterPlaceholderFactory):
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

    def __init__(
        self,
        hash_length: int = 8,
        prefix: str = DEFAULT_PREFIX,
        suffix: str = DEFAULT_SUFFIX,
    ) -> None:
        """Store the digest length to keep and the token delimiters."""
        super().__init__(prefix, suffix)
        self.hash_length = hash_length

    def _token(self, label: str, number: int) -> PreservesLabeledIdentityOpaque:
        """Render a label and its ordinal as the <<LABEL:hash>> token."""
        seed = f"{label}:{number}"
        digest = hashlib.sha256(seed.encode()).hexdigest()
        token = self._wrap(f"{label}:{digest[: self.hash_length]}")
        return PreservesLabeledIdentityOpaque(token)
