"""Detector configuration models, discriminated on type."""

import re
from typing import Annotated, Literal

from pydantic import Discriminator, Field, field_validator

from piighost.components.detector import CompositeDetector, RegexDetector
from piighost.components.detector.base import AnyDetector
from piighost.config.models.common import _ComponentConfig


class RegexDetectorConfig(_ComponentConfig):
    """Config for the regex detector, one pattern per label."""

    type: Literal["regex"]
    patterns: dict[str, str] = Field(min_length=1)

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
