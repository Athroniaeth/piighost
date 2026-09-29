"""Overlap resolver configuration model."""

from typing import Annotated, Literal

from pydantic import Field

from piighost.components.overlap_resolver.base import AnyOverlapResolver
from piighost.config.models.common import _ComponentConfig


class ConfidenceOverlapResolverConfig(_ComponentConfig):
    """Config for the confidence overlap resolver, keeping the surest span."""

    type: Literal["confidence"]

    def build(self) -> AnyOverlapResolver:
        """Build a ConfidenceOverlapResolver."""
        from piighost.components.overlap_resolver.confidence import (
            ConfidenceOverlapResolver,
        )

        return ConfidenceOverlapResolver()


class MergeOverlapResolverConfig(_ComponentConfig):
    """Config for the merge overlap resolver, keeping the union of overlapping spans."""

    type: Literal["merge"]

    def build(self) -> AnyOverlapResolver:
        """Build a MergeOverlapResolver."""
        from piighost.components.overlap_resolver.merge import MergeOverlapResolver

        return MergeOverlapResolver()


OverlapResolverConfig = Annotated[
    ConfidenceOverlapResolverConfig | MergeOverlapResolverConfig,
    Field(discriminator="type"),
]
"""The overlap resolver configuration, discriminated on type."""
