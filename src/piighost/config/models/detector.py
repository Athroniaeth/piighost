"""Detector configuration models, discriminated on type."""

import re
from typing import Annotated, Literal, Self

from pydantic import Discriminator, Field, field_validator, model_validator

from piighost.catalog import CatalogRefError, parse_ref, pull
from piighost.components.detector import (
    ChunkedDetector,
    CompositeDetector,
    ExactMatchDetector,
    RegexDetector,
)
from piighost.components.detector.base import AnyDetector
from piighost.config.models.common import _ComponentConfig
from piighost.config.models.detector_model import (
    Gliner2DetectorConfig,
    LLMDetectorConfig,
    PresidioDetectorConfig,
    SpacyDetectorConfig,
    TransformersDetectorConfig,
)
from piighost.text import RecursiveCharacterTextSplitter

_REMOVED_CATALOGS = frozenset({"generic", "us", "eu", "fr"})
"""The names of the catalogs piighost shipped before 2.0, now catalog groups.

A config still naming one is refused with the catalog reference that replaces it,
rather than with a bare parse error.
"""


class RegexDetectorConfig(_ComponentConfig):
    """Config for the regex detector, patterns from inline entries and catalogs.

    The final pattern set merges the catalogs in order, then the inline
    patterns, so an inline pattern overrides a catalog pattern on the same label.

    A catalog is a reference, written catalog:namespace/name with an optional
    :selector, or hub:namespace/name as 1.x wrote it. It is fetched when the
    config is built, so a pipeline names a reviewed pattern group instead of
    carrying a copy of it.

    Attributes:
        patterns: Inline label to regex mappings, optional when a catalog is set.
        catalogs: Catalog references to pull, such as catalog:piighost/generic.
    """

    type: Literal["regex"]
    patterns: dict[str, str] = Field(default_factory=dict)
    catalogs: list[str] = Field(default_factory=list)

    @field_validator("catalogs")
    @classmethod
    def _catalogs_are_refs(cls, catalogs: list[str]) -> list[str]:
        """Reject a catalog that is not a catalog reference.

        Without this a typo parses fine and fails at build time, or worse
        reaches the network as a malformed URL.
        """
        for catalog in catalogs:
            if catalog in _REMOVED_CATALOGS:
                raise ValueError(
                    f"the built-in catalog {catalog!r} was removed in piighost "
                    f"2.0: name the catalog group instead, catalog:piighost/{catalog}"
                )
            try:
                parse_ref(catalog)
            except CatalogRefError as exc:
                raise ValueError(
                    f"unknown catalog {catalog!r}: expected a catalog reference "
                    f"such as catalog:piighost/generic"
                ) from exc
        return catalogs

    @field_validator("patterns")
    @classmethod
    def _patterns_are_compilable(cls, patterns: dict[str, str]) -> dict[str, str]:
        """Reject a pattern that is not a compilable regex at load time.

        Without this a malformed pattern parses fine and only raises a raw
        re.error later, when the detector first runs; validating here turns it
        into a configuration error the caller sees at load time.
        """
        for label, pattern in patterns.items():
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(
                    f"pattern for label {label} is not a valid regex: {exc}"
                ) from exc
        return patterns

    @model_validator(mode="after")
    def _has_some_patterns(self) -> Self:
        """Require at least one inline pattern or one catalog."""
        if not self.patterns and not self.catalogs:
            raise ValueError("a regex detector needs inline patterns or a catalog")
        return self

    def build(self) -> AnyDetector:
        """Build a RegexDetector over the merged catalog and inline patterns.

        A catalog reference is fetched here, so building a
        config that names one reaches the network. A reference pinned to a
        commit is cached on disk after the first build.

        Raises:
            CatalogError: If a catalog cannot be pulled.
        """
        merged: dict[str, str] = {}
        for catalog in self.catalogs:
            merged.update(pull(catalog))
        merged.update(self.patterns)
        return RegexDetector(merged)


class CompositeDetectorConfig(_ComponentConfig):
    """Config for the composite detector, running child detectors together."""

    type: Literal["composite"]
    detectors: "list[DetectorConfig]" = Field(min_length=1)

    def build(self) -> AnyDetector:
        """Build a CompositeDetector from the built child detectors."""
        children = [detector.build() for detector in self.detectors]
        return CompositeDetector(children)


class ExactMatchDetectorConfig(_ComponentConfig):
    """Config for the exact-match detector, literal values mapped to labels."""

    type: Literal["exact"]
    values: dict[str, str] = Field(min_length=1)

    def build(self) -> AnyDetector:
        """Build an ExactMatchDetector over the configured values."""
        return ExactMatchDetector(self.values)


class ChunkedDetectorConfig(_ComponentConfig):
    """Config for the chunked detector, wrapping a detector with a splitter.

    Attributes:
        detector: The detector run on each chunk.
        chunk_size: The maximum size of a chunk the splitter emits.
        chunk_overlap: The overlap kept between consecutive chunks.
    """

    type: Literal["chunked"]
    detector: "DetectorConfig"
    chunk_size: int = Field(default=1000, gt=0)
    chunk_overlap: int = Field(default=100, ge=0)

    @model_validator(mode="after")
    def _overlap_below_size(self) -> Self:
        """Require the overlap to stay below the chunk size."""
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self

    def build(self) -> AnyDetector:
        """Build a ChunkedDetector wrapping the built inner detector."""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap
        )
        detector = self.detector.build()
        return ChunkedDetector(detector, splitter=splitter)


DetectorConfig = Annotated[
    RegexDetectorConfig
    | CompositeDetectorConfig
    | ExactMatchDetectorConfig
    | ChunkedDetectorConfig
    | Gliner2DetectorConfig
    | SpacyDetectorConfig
    | TransformersDetectorConfig
    | PresidioDetectorConfig
    | LLMDetectorConfig,
    Discriminator("type"),
]


CompositeDetectorConfig.model_rebuild()
ChunkedDetectorConfig.model_rebuild()
