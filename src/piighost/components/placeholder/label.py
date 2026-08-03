"""Label placeholder factory: one token per label, revealing the type."""

from piighost.models import Entity
from piighost.components.placeholder.base import AnyPlaceholderFactory
from piighost.components.placeholder.tags import PreservesLabel


class LabelPlaceholderFactory(AnyPlaceholderFactory[PreservesLabel]):
    """Map every entity to a token naming its label.

    Each entity becomes <<LABEL>>, such as <<PERSON>>, so a reader learns the
    entity type but nothing that tells two entities of one label apart. Every
    person collapses to <<PERSON>>, which cannot be reversed, hence the tag
    PreservesLabel.
    """

    def create(self, entities: list[Entity]) -> dict[Entity, PreservesLabel]:
        """Return a label-naming token for every entity."""
        return {entity: PreservesLabel(f"<<{entity.label}>>") for entity in entities}
