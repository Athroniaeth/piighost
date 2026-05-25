"""Entity linker configuration models."""

from typing import Annotated, Literal

from pydantic import Discriminator

from piighost.config.models.common import _ComponentConfig


class ExactEntityLinkerConfig(_ComponentConfig):
    type: Literal["exact"] = "exact"


class DisabledEntityLinkerConfig(_ComponentConfig):
    type: Literal["disabled"]


EntityLinkerConfig = Annotated[
    ExactEntityLinkerConfig | DisabledEntityLinkerConfig,
    Discriminator("type"),
]
