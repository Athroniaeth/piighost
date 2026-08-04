"""Placeholder factory configuration models, discriminated on type."""

from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.components.placeholder import (
    LabelCounterPlaceholderFactory,
    LabelPlaceholderFactory,
    MaskPlaceholderFactory,
    RedactPlaceholderFactory,
)
from piighost.components.placeholder.base import AnyPlaceholderFactory
from piighost.components.placeholder.tags import PlaceholderPreservation
from piighost.config.models.common import _ComponentConfig


class RedactPlaceholderConfig(_ComponentConfig):
    """Config for the redact factory, one constant token for every entity."""

    type: Literal["redact"]

    def build(self) -> AnyPlaceholderFactory[PlaceholderPreservation]:
        """Build the redact placeholder factory."""
        return RedactPlaceholderFactory()


class LabelPlaceholderConfig(_ComponentConfig):
    """Config for the label factory, one token per label."""

    type: Literal["label"]

    def build(self) -> AnyPlaceholderFactory[PlaceholderPreservation]:
        """Build the label placeholder factory."""
        return LabelPlaceholderFactory()


class LabelCounterPlaceholderConfig(_ComponentConfig):
    """Config for the label-counter factory, a numbered token per label."""

    type: Literal["label_counter"]

    def build(self) -> AnyPlaceholderFactory[PlaceholderPreservation]:
        """Build the label-counter placeholder factory."""
        return LabelCounterPlaceholderFactory()


class MaskPlaceholderConfig(_ComponentConfig):
    """Config for the mask factory, keeping a few leading characters."""

    type: Literal["mask"]
    visible: int = Field(default=1, ge=0)
    mask_char: str = Field(default="*", min_length=1, max_length=1)

    def build(self) -> AnyPlaceholderFactory[PlaceholderPreservation]:
        """Build the mask placeholder factory with its visible count and char."""
        return MaskPlaceholderFactory(visible=self.visible, mask_char=self.mask_char)


PlaceholderConfig = Annotated[
    RedactPlaceholderConfig
    | LabelPlaceholderConfig
    | LabelCounterPlaceholderConfig
    | MaskPlaceholderConfig,
    Discriminator("type"),
]
