"""Detector configuration models (discriminated union on ``type``)."""

from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.config.models.common import _ComponentConfig


class RegexDetectorConfig(_ComponentConfig):
    type: Literal["regex"]
    name: str | None = None
    patterns: dict[str, str] = Field(min_length=1)


class Gliner2DetectorConfig(_ComponentConfig):
    type: Literal["gliner2"]
    name: str | None = None
    model: str
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    labels: list[str] = Field(min_length=1)
    flat_ner: bool = True


class SpacyDetectorConfig(_ComponentConfig):
    type: Literal["spacy"]
    name: str | None = None
    model: str
    labels: list[str] = Field(min_length=1)


class TransformersDetectorConfig(_ComponentConfig):
    type: Literal["transformers"]
    name: str | None = None
    model: str
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class LLMDetectorConfig(_ComponentConfig):
    type: Literal["llm"]
    name: str | None = None
    provider: str
    model: str
    labels: list[str] = Field(min_length=1)


class ChunkedDetectorConfig(_ComponentConfig):
    type: Literal["chunked"]
    name: str | None = None
    chunk_size: int = Field(ge=1)
    overlap: int = Field(default=0, ge=0)
    inner: "DetectorConfig"


DetectorConfig = Annotated[
    RegexDetectorConfig
    | Gliner2DetectorConfig
    | SpacyDetectorConfig
    | TransformersDetectorConfig
    | LLMDetectorConfig
    | ChunkedDetectorConfig,
    Discriminator("type"),
]


# Resolve the self-reference in ChunkedDetectorConfig.inner.
ChunkedDetectorConfig.model_rebuild()
