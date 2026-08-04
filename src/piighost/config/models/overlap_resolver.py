"""Overlap resolver configuration model."""

from typing import Literal

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


OverlapResolverConfig = ConfidenceOverlapResolverConfig
"""The overlap resolver configuration.

A plain alias while one resolver exists; it becomes a discriminated union when a
second resolver lands.
"""
