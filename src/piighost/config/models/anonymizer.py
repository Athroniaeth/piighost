"""Anonymizer configuration model."""

from piighost.components.anonymizer import Anonymizer
from piighost.components.anonymizer.base import AnyAnonymizer
from piighost.components.placeholder.tags import PlaceholderPreservation
from piighost.config.models.common import _ComponentConfig
from piighost.config.models.placeholder import PlaceholderConfig


class AnonymizerConfig(_ComponentConfig):
    """Config for the anonymizer, built on a placeholder factory."""

    placeholder: PlaceholderConfig

    def build(self) -> AnyAnonymizer[PlaceholderPreservation]:
        """Build an Anonymizer on the configured placeholder factory."""
        return Anonymizer(self.placeholder.build())
