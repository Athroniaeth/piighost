"""Model-backed detector configuration models, discriminated on type.

Each config needs an optional extra, so build() imports the concrete detector
lazily and a missing extra surfaces as the component's own ImportError naming
the extra to install. The port AnyDetector is imported at module top only for
the build() return annotation.
"""

from typing import Annotated, Literal

from pydantic import Field

from piighost.components.detector.base import AnyDetector
from piighost.config.models.common import _ComponentConfig

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
"""A confidence score, from 0 to 1."""

Threshold = Confidence | dict[str, Confidence]
"""One threshold for every label, or one per external label.

A mapping covers the labels it does not name with its __default key, as in
threshold = { __default = 0.5, ADDRESS = 0.9 }. The detector refuses a mapping
that names a label it does not emit, or leaves one out without __default.
"""


class Gliner2DetectorConfig(_ComponentConfig):
    """Config for the GLiNER2 detector, a zero-shot NER model."""

    type: Literal["gliner2"]
    model: str
    labels: list[str] | dict[str, str]
    threshold: Threshold = 0.5
    max_concurrency: int | None = Field(default=None, ge=1)
    max_chars: int | None = Field(default=None, ge=1)

    def build(self) -> AnyDetector:
        """Build a Gliner2Detector loading the named model."""
        from piighost.components.detector.ner.gliner2 import Gliner2Detector

        return Gliner2Detector(
            model=self.model,
            labels=self.labels,
            threshold=self.threshold,
            max_concurrency=self.max_concurrency,
            max_chars=self.max_chars,
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
    threshold: Threshold = 0.0
    max_concurrency: int | None = Field(default=None, ge=1)
    max_chars: int | None = Field(default=None, ge=1)
    aggregation_strategy: str = "simple"

    def build(self) -> AnyDetector:
        """Build a TransformersDetector from the named model.

        The model field is passed to the detector's pipeline parameter, which
        accepts a model name and builds the token-classification pipeline with the
        given aggregation_strategy, so sub-word tokens are grouped into whole
        entities.
        """
        from piighost.components.detector.ner.transformers import TransformersDetector

        return TransformersDetector(
            pipeline=self.model,
            labels=self.labels,
            threshold=self.threshold,
            max_concurrency=self.max_concurrency,
            max_chars=self.max_chars,
            aggregation_strategy=self.aggregation_strategy,
        )


class PresidioDetectorConfig(_ComponentConfig):
    """Config for the Presidio detector, wrapping a default AnalyzerEngine.

    The config path builds Presidio's default English AnalyzerEngine with its
    default recognizers. Other languages, custom recognizers, or a custom NLP
    engine are the programmatic path, constructing the engine and passing it to
    PresidioDetector directly.
    """

    type: Literal["presidio"]
    labels: list[str] | dict[str, str] | None = None
    language: str = "en"
    threshold: Threshold = 0.0

    def build(self) -> AnyDetector:
        """Build a PresidioDetector over Presidio's default AnalyzerEngine."""
        from piighost.components.detector.ner.presidio import (
            AnalyzerEngine,
            PresidioDetector,
        )

        analyzer = AnalyzerEngine()
        return PresidioDetector(
            analyzer=analyzer,
            labels=self.labels,
            language=self.language,
            threshold=self.threshold,
        )


class LLMDetectorConfig(_ComponentConfig):
    """Config for the LLM detector, extracting entities via a chat model."""

    type: Literal["llm"]
    model: str
    labels: list[str] | dict[str, str]
    prompt: str | None = None
    provider: str | None = None
    fail_open: bool = False

    def build(self) -> AnyDetector:
        """Build an LLMDetector from the model, labels, prompt, and provider."""
        from piighost.components.detector.llm import LLMDetector

        return LLMDetector(
            model=self.model,
            labels=self.labels,
            prompt=self.prompt,
            provider=self.provider,
            fail_open=self.fail_open,
        )
