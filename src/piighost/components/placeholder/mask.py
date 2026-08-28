"""Mask placeholder factory: keep a leading fragment, star out the rest."""

from piighost.components.placeholder.base import AnyPlaceholderFactory
from piighost.components.placeholder.tags import PreservesShape
from piighost.models import Entity


class MaskPlaceholderFactory(AnyPlaceholderFactory[PreservesShape]):
    """Reveal a few leading characters of a value and mask the rest.

    A value keeps its first characters and replaces every other one with the
    mask character, so Jonathan becomes J*******. The length is preserved and a
    fragment leaks, which is why the tag is PreservesShape: two values with the
    same prefix and length collide on one token, so it does not identify an
    entity and cannot be reversed.

    Short values are guarded: the token never reveals the whole value and always
    masks at least one character, so a single-character value becomes one mask
    character rather than itself. The reveal count is therefore capped at the
    length minus one.

    Attributes:
        visible: How many leading characters to keep at most.
        mask_char: The character each masked position is replaced with.
    """

    def __init__(self, visible: int = 1, mask_char: str = "*") -> None:
        """Store how many leading characters to keep and the mask character."""
        self.visible = visible
        self.mask_char = mask_char

    def create(self, entities: list[Entity]) -> dict[Entity, PreservesShape]:
        """Return a masked form of every entity's value."""
        return {entity: self._mask(entity.text) for entity in entities}

    def _mask(self, value: str) -> PreservesShape:
        """Keep the leading fragment of value, mask the rest, never all of it."""
        # Cap the reveal at len - 1 so at least one character is always masked
        # and the whole value is never exposed, however short it is.
        kept = min(self.visible, max(len(value) - 1, 0))
        masked = value[:kept] + self.mask_char * (len(value) - kept)
        return PreservesShape(masked)
