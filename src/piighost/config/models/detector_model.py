"""Model-backed detector configuration models, discriminated on type.

Each config needs an optional extra, so build() imports the concrete detector
lazily and a missing extra surfaces as the component's own ImportError naming
the extra to install. The port AnyDetector is imported at module top only for
the build() return annotation.
"""

from typing import Literal

from pydantic import Field

from piighost.components.detector.base import AnyDetector
from piighost.config.models.common import _ComponentConfig


class Gliner2DetectorConfig(_ComponentConfig):
    """Config for the GLiNER2 detector, a zero-shot NER model."""

    type: Literal["gliner2"]
    model: str
    labels: list[str] | dict[str, str]
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    max_concurrency: int | None = Field(default=None, ge=1)

    def build(self) -> AnyDetector:
        """Build a Gliner2Detector loading the named model."""
        from piighost.components.detector.ner.gliner2 import Gliner2Detector

        return Gliner2Detector(
            model=self.model,
            labels=self.labels,
            threshold=self.threshold,
            max_concurrency=self.max_concurrency,
        )


class SpacyDetectorConfig(_ComponentConfig):
    """Config for the spaCy detector, a pipeline NER model."""

    type: Literal["spacy"]
    model: str
    labels: list[str] | dict[str, str] | None = None
    max_concurrency: int | None = Field(default=None, ge=1)

    def build(self) -> AnyDetector:
        """Build a SpacyDetector loading the named pipeline."""
        from piighost.components.detector.ner.spacy import SpacyDetector

        return SpacyDetector(
            model=self.model,
            labels=self.labels,
            max_concurrency=self.max_concurrency,
        )


class TransformersDetectorConfig(_ComponentConfig):
    """Config for the Transformers detector, a token-classification pipeline."""

    type: Literal["transformers"]
    model: str
    labels: list[str] | dict[str, str] | None = None
    threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    max_concurrency: int | None = Field(default=None, ge=1)

    def build(self) -> AnyDetector:
        """Build a TransformersDetector from the named model.

        The model field is passed to the detector's pipeline parameter, which
        accepts a model name and builds the token-classification pipeline.
        """
        from piighost.components.detector.ner.transformers import TransformersDetector

        return TransformersDetector(
            pipeline=self.model,
            labels=self.labels,
            threshold=self.threshold,
            max_concurrency=self.max_concurrency,
        )


class LLMDetectorConfig(_ComponentConfig):
    """Config for the LLM detector, extracting entities via a chat model."""

    type: Literal["llm"]
    model: str
    labels: list[str] | dict[str, str]
    prompt: str | None = None
    provider: str | None = None

    def build(self) -> AnyDetector:
        """Build an LLMDetector from the model, labels, prompt, and provider."""
        from piighost.components.detector.llm import LLMDetector

        return LLMDetector(
            model=self.model,
            labels=self.labels,
            prompt=self.prompt,
            provider=self.provider,
        )
