"""Entity linker configuration models."""

from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.config.models.common import _ComponentConfig


class ExactEntityLinkerConfig(_ComponentConfig):
    type: Literal["exact"] = "exact"
    min_text_length: int = Field(default=1, ge=1)
    case_sensitive: bool = False


class DisabledEntityLinkerConfig(_ComponentConfig):
    type: Literal["disabled"]


EntityLinkerConfig = Annotated[
    ExactEntityLinkerConfig | DisabledEntityLinkerConfig,
    Discriminator("type"),
]
