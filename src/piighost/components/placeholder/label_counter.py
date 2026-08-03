"""Label counter placeholder factory: <<LABEL:n>> tokens, unique per entity."""

from piighost.components.placeholder.base import BaseCounterPlaceholderFactory
from piighost.components.placeholder.tags import PreservesLabeledIdentityOpaque


class LabelCounterPlaceholderFactory(BaseCounterPlaceholderFactory):
    """Number each entity within its label, as <<LABEL:n>>.

    The first person becomes <<PERSON:1>>, the second <<PERSON:2>>, while an
    email starts its own count at <<EMAIL:1>>. Every entity gets a distinct token
    that also names its label, so the mapping reveals the type yet stays
    reversible, hence the tag PreservesLabeledIdentityOpaque. The count follows
    the entity order, so the same entity list always yields the same tokens.
    """

    def _token(self, label: str, number: int) -> PreservesLabeledIdentityOpaque:
        """Render one label and its ordinal as the <<LABEL:n>> token."""
        token = self._wrap(f"{label}:{number}")
        return PreservesLabeledIdentityOpaque(token)
