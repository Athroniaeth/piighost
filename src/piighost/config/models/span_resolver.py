"""Span conflict resolver configuration models."""

from typing import Annotated, Literal

from pydantic import Discriminator

from piighost.config.models.common import _ComponentConfig


class ConfidenceSpanResolverConfig(_ComponentConfig):
    type: Literal["confidence"] = "confidence"


class DisabledSpanResolverConfig(_ComponentConfig):
    type: Literal["disabled"]


SpanResolverConfig = Annotated[
    ConfidenceSpanResolverConfig | DisabledSpanResolverConfig,
    Discriminator("type"),
]
