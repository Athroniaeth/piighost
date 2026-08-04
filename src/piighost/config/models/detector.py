"""Detector configuration models, discriminated on type."""

from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.components.detector import CompositeDetector, RegexDetector
from piighost.components.detector.base import AnyDetector
from piighost.config.models.common import _ComponentConfig


class RegexDetectorConfig(_ComponentConfig):
    """Config for the regex detector, one pattern per label."""

    type: Literal["regex"]
    patterns: dict[str, str] = Field(min_length=1)

    def build(self) -> AnyDetector:
        """Build a RegexDetector over the configured patterns."""
        return RegexDetector(self.patterns)


class CompositeDetectorConfig(_ComponentConfig):
    """Config for the composite detector, running child detectors together."""

    type: Literal["composite"]
    detectors: "list[DetectorConfig]" = Field(min_length=1)

    def build(self) -> AnyDetector:
        """Build a CompositeDetector from the built child detectors."""
        children = [detector.build() for detector in self.detectors]
        return CompositeDetector(children)


DetectorConfig = Annotated[
    RegexDetectorConfig | CompositeDetectorConfig,
    Discriminator("type"),
]


CompositeDetectorConfig.model_rebuild()
