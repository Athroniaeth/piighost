"""Entity resolver configuration models, discriminated on type."""

from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.components.entity_resolver.base import AnyEntityResolver
from piighost.config.models.common import _ComponentConfig

_DEFAULT_FUZZY_THRESHOLD = 0.85
"""Default Jaro-Winkler similarity above which two entities are clustered."""


class MergeEntityResolverConfig(_ComponentConfig):
    """Config for the merge resolver, unioning entities that share detections."""

    type: Literal["merge"]

    def build(self) -> AnyEntityResolver:
        """Build a MergeEntityResolver."""
        from piighost.components.entity_resolver.merge import MergeEntityResolver

        return MergeEntityResolver()


class SeparateEntityResolverConfig(_ComponentConfig):
    """Config for the separate resolver, keeping every entity distinct."""

    type: Literal["separate"]

    def build(self) -> AnyEntityResolver:
        """Build a SeparateEntityResolver."""
        from piighost.components.entity_resolver.separate import SeparateEntityResolver

        return SeparateEntityResolver()


class FuzzyEntityResolverConfig(_ComponentConfig):
    """Config for the fuzzy resolver, clustering near-duplicate entities."""

    type: Literal["fuzzy"]
    threshold: float = Field(default=_DEFAULT_FUZZY_THRESHOLD, ge=0.0, le=1.0)

    def build(self) -> AnyEntityResolver:
        """Build a FuzzyEntityResolver over the configured threshold."""
        from piighost.components.entity_resolver.fuzzy import FuzzyEntityResolver

        return FuzzyEntityResolver(threshold=self.threshold)


EntityResolverConfig = Annotated[
    MergeEntityResolverConfig
    | SeparateEntityResolverConfig
    | FuzzyEntityResolverConfig,
    Discriminator("type"),
]
