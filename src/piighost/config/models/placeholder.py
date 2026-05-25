"""Placeholder factory configuration models."""

from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.config.models.common import _ComponentConfig


class LabelCounterPlaceholderConfig(_ComponentConfig):
    type: Literal["label_counter"] = "label_counter"


class LabelHashPlaceholderConfig(_ComponentConfig):
    type: Literal["label_hash"]
    hash_length: int = Field(default=8, ge=4, le=64)


class LabelPlaceholderConfig(_ComponentConfig):
    type: Literal["label"]


class MaskPlaceholderConfig(_ComponentConfig):
    type: Literal["mask"]
    mask_char: str = Field(default="*", min_length=1, max_length=1)


class RedactCounterPlaceholderConfig(_ComponentConfig):
    type: Literal["redact_counter"]


class RedactHashPlaceholderConfig(_ComponentConfig):
    type: Literal["redact_hash"]
    hash_length: int = Field(default=8, ge=4, le=64)


class RedactPlaceholderConfig(_ComponentConfig):
    type: Literal["redact"]


class FakerCounterPlaceholderConfig(_ComponentConfig):
    type: Literal["faker_counter"]
    locale: str = "en_US"


class FakerHashPlaceholderConfig(_ComponentConfig):
    type: Literal["faker_hash"]
    locale: str = "en_US"
    hash_length: int = Field(default=8, ge=4, le=64)


class FakerPlaceholderConfig(_ComponentConfig):
    type: Literal["faker"]
    locale: str = "en_US"


PlaceholderFactoryConfig = Annotated[
    LabelCounterPlaceholderConfig
    | LabelHashPlaceholderConfig
    | LabelPlaceholderConfig
    | MaskPlaceholderConfig
    | RedactCounterPlaceholderConfig
    | RedactHashPlaceholderConfig
    | RedactPlaceholderConfig
    | FakerCounterPlaceholderConfig
    | FakerHashPlaceholderConfig
    | FakerPlaceholderConfig,
    Discriminator("type"),
]
