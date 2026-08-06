"""Detector configuration models, discriminated on type."""

import re
from typing import Annotated, Literal, Self

from pydantic import Discriminator, Field, field_validator, model_validator

from piighost.components.detector import (
    ChunkedDetector,
    CompositeDetector,
    ExactMatchDetector,
    RegexDetector,
)
from piighost.components.detector.base import AnyDetector
from piighost.components.detector.patterns import (
    EU_PATTERNS,
    FR_PATTERNS,
    GENERIC_PATTERNS,
    US_PATTERNS,
)
from piighost.config.models.common import _ComponentConfig
from piighost.config.models.detector_model import (
    Gliner2DetectorConfig,
    LLMDetectorConfig,
    SpacyDetectorConfig,
    TransformersDetectorConfig,
)
from piighost.text import RecursiveCharacterTextSplitter

CatalogName = Literal["generic", "us", "eu", "fr"]
"""The prebuilt catalog names a regex detector config can pull patterns from."""

_CATALOGS: dict[str, dict[str, str]] = {
    "generic": GENERIC_PATTERNS,
    "us": US_PATTERNS,
    "eu": EU_PATTERNS,
    "fr": FR_PATTERNS,
}
"""The prebuilt pattern catalogs a regex detector config can pull by name."""


class RegexDetectorConfig(_ComponentConfig):
    """Config for the regex detector, patterns from inline entries and catalogs.

    The final pattern set merges the named catalogs first, then the inline
    patterns, so an inline pattern overrides a catalog pattern on the same label.

    Attributes:
        patterns: Inline label to regex mappings, optional when a catalog is set.
        catalogs: Names of prebuilt catalogs to pull, among generic, us, eu, fr.
    """

    type: Literal["regex"]
    patterns: dict[str, str] = Field(default_factory=dict)
    catalogs: list[CatalogName] = Field(default_factory=list)

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
        """Build a RegexDetector over the merged catalog and inline patterns."""
        merged: dict[str, str] = {}
        for name in self.catalogs:
            merged.update(_CATALOGS[name])
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
    | LLMDetectorConfig,
    Discriminator("type"),
]


CompositeDetectorConfig.model_rebuild()
ChunkedDetectorConfig.model_rebuild()
