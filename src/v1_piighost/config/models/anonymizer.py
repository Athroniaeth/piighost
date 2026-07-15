"""Anonymizer configuration models."""

from typing import Literal

from pydantic import Field

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


# Only one anonymizer variant exists today. A single-member discriminated union
# is rejected by pydantic >= 2.12 ("Discriminator must be used with a Union
# type"), so alias the concrete config directly. When a second anonymizer type
# is added, switch back to a real union:
#   AnonymizerConfig = Annotated[DefaultAnonymizerConfig | OtherConfig, Discriminator("type")]
AnonymizerConfig = DefaultAnonymizerConfig
