"""Top-level pipeline configuration and manifest."""

from typing import Literal

from pydantic import Field

from piighost.config.models.anonymizer import (
    AnonymizerConfig,
    DefaultAnonymizerConfig,
)
from piighost.config.models.common import _ComponentConfig
from piighost.config.models.detector import DetectorConfig
from piighost.config.models.entity_linker import (
    EntityLinkerConfig,
    ExactEntityLinkerConfig,
)
from piighost.config.models.entity_resolver import (
    EntityResolverConfig,
    MergeEntityResolverConfig,
)
from piighost.config.models.span_resolver import (
    ConfidenceSpanResolverConfig,
    SpanResolverConfig,
)


class PipelineMeta(_ComponentConfig):
    """Free-text metadata for the pipeline. Exposed by ``/v1/labels``."""

    name: str | None = None
    description: str | None = None
    schema_version: Literal[1] = 1


class PipelineConfig(_ComponentConfig):
    """Root model for a piighost pipeline TOML configuration."""

    pipeline: PipelineMeta = Field(default_factory=PipelineMeta)
    detectors: list[DetectorConfig] = Field(min_length=1)
    span_resolver: SpanResolverConfig = Field(
        default_factory=ConfidenceSpanResolverConfig
    )
    entity_linker: EntityLinkerConfig = Field(default_factory=ExactEntityLinkerConfig)
    entity_resolver: EntityResolverConfig = Field(
        default_factory=MergeEntityResolverConfig
    )
    anonymizer: AnonymizerConfig = Field(default_factory=DefaultAnonymizerConfig)
