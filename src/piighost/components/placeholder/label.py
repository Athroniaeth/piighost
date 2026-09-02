"""Label placeholder factory: one token per label, revealing the type."""

from piighost.components.placeholder.base import (
    AnyPlaceholderFactory,
    BaseDelimitedPlaceholderFactory,
)
from piighost.components.placeholder.streaming import LABEL_INNER
from piighost.components.placeholder.tags import PreservesLabel
from piighost.models import Entity


class LabelPlaceholderFactory(
    BaseDelimitedPlaceholderFactory, AnyPlaceholderFactory[PreservesLabel]
):
    """Map every entity to a token naming its label.

    Each entity becomes <<LABEL>>, such as <<PERSON>>, so a reader learns the
    entity type but nothing that tells two entities of one label apart. Every
    person collapses to <<PERSON>>, which cannot be reversed, hence the tag
    PreservesLabel.
    """

    _inner_pattern: str = LABEL_INNER
    """These tokens carry a bare label, with no colon-separated identifier."""

    def create(self, entities: list[Entity]) -> dict[Entity, PreservesLabel]:
        """Return a label-naming token for every entity."""
        return {entity: PreservesLabel(self._wrap(entity.label)) for entity in entities}
