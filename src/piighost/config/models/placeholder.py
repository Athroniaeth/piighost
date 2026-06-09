"""Placeholder factory configuration models."""

from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.config.models.common import _ComponentConfig


class LabelCounterPlaceholderConfig(_ComponentConfig):
    type: Literal["label_counter"] = "label_counter"


class LabelHashPlaceholderConfig(_ComponentConfig):
    type: Literal["label_hash"]
    hash_length: int = Field(default=8, ge=4, le=64)
    # The process-wide pepper stays out of TOML; it comes from the
    # ``PIIGHOST_HASH_PEPPER`` env var. Only the per-instance salt is here.
    salt: str = ""


class LabelPlaceholderConfig(_ComponentConfig):
    type: Literal["label"]


class MaskPlaceholderConfig(_ComponentConfig):
    type: Literal["mask"]
    mask_char: str = Field(default="*", min_length=1, max_length=1)
    visible_chars: int = Field(default=4, ge=0)


class RedactCounterPlaceholderConfig(_ComponentConfig):
    type: Literal["redact_counter"]
    prefix: str = "REDACT"


class RedactHashPlaceholderConfig(_ComponentConfig):
    type: Literal["redact_hash"]
    hash_length: int = Field(default=8, ge=4, le=64)
    prefix: str = "REDACT"
    # The process-wide pepper stays out of TOML; it comes from the
    # ``PIIGHOST_HASH_PEPPER`` env var. Only the per-instance salt is here.
    salt: str = ""


class RedactPlaceholderConfig(_ComponentConfig):
    type: Literal["redact"]
    value: str = "REDACT"


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
