"""Span conflict resolver configuration models."""

from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.config.models.common import _ComponentConfig


class ConfidenceSpanResolverConfig(_ComponentConfig):
    type: Literal["confidence"] = "confidence"
    confidence_threshold: float = Field(default=0.0, ge=0.0, le=1.0)


class DisabledSpanResolverConfig(_ComponentConfig):
    type: Literal["disabled"]


SpanResolverConfig = Annotated[
    ConfidenceSpanResolverConfig | DisabledSpanResolverConfig,
    Discriminator("type"),
]
