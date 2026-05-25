"""Anonymizer configuration models."""

from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.config.models.common import _ComponentConfig
from piighost.config.models.placeholder import (
    LabelCounterPlaceholderConfig,
    PlaceholderFactoryConfig,
)


class DefaultAnonymizerConfig(_ComponentConfig):
    type: Literal["default"] = "default"
    placeholder_factory: PlaceholderFactoryConfig = Field(
        default_factory=LabelCounterPlaceholderConfig
    )


AnonymizerConfig = Annotated[
    DefaultAnonymizerConfig,
    Discriminator("type"),
]
