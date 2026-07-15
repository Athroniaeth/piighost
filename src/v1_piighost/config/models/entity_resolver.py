"""Entity conflict resolver configuration models."""

from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.config.models.common import _ComponentConfig


class MergeEntityResolverConfig(_ComponentConfig):
    type: Literal["merge"] = "merge"


class FuzzyEntityResolverConfig(_ComponentConfig):
    type: Literal["fuzzy"]
    threshold: float = Field(default=0.85, ge=0.0, le=1.0)


class DisabledEntityResolverConfig(_ComponentConfig):
    type: Literal["disabled"]


EntityResolverConfig = Annotated[
    MergeEntityResolverConfig
    | FuzzyEntityResolverConfig
    | DisabledEntityResolverConfig,
    Discriminator("type"),
]
