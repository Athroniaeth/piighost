"""Type-mapping factories for ``piighost.config``.

Each ``build_*`` function dispatches on the concrete config class
(which Pydantic has already discriminated) to the matching component
class's ``from_config`` classmethod. Mappings are plain ``dict``s
keyed on the config type so dispatch is O(1) and trivially auditable.

Imports of the GLiNER / spaCy / transformers / LLM detector classes
are deferred to inside ``build_detector`` to keep ``piighost.config``
importable without their optional dependencies installed.
"""

from typing import TYPE_CHECKING

from pydantic import BaseModel

from piighost.anonymizer import Anonymizer
from piighost.config.models.anonymizer import DefaultAnonymizerConfig
from piighost.config.models.detector import (
    ChunkedDetectorConfig,
    Gliner2DetectorConfig,
    LLMDetectorConfig,
    RegexDetectorConfig,
    SpacyDetectorConfig,
    TransformersDetectorConfig,
)
from piighost.config.models.entity_linker import (
    DisabledEntityLinkerConfig,
    ExactEntityLinkerConfig,
)
from piighost.config.models.entity_resolver import (
    DisabledEntityResolverConfig,
    FuzzyEntityResolverConfig,
    MergeEntityResolverConfig,
)
from piighost.config.models.placeholder import (
    FakerCounterPlaceholderConfig,
    FakerHashPlaceholderConfig,
    FakerPlaceholderConfig,
    LabelCounterPlaceholderConfig,
    LabelHashPlaceholderConfig,
    LabelPlaceholderConfig,
    MaskPlaceholderConfig,
    RedactCounterPlaceholderConfig,
    RedactHashPlaceholderConfig,
    RedactPlaceholderConfig,
)
from piighost.config.models.span_resolver import (
    ConfidenceSpanResolverConfig,
    DisabledSpanResolverConfig,
)
from piighost.detector.base import RegexDetector
from piighost.linker.entity import DisabledEntityLinker, ExactEntityLinker
from piighost.placeholder import (
    LabelCounterPlaceholderFactory,
    LabelHashPlaceholderFactory,
    LabelPlaceholderFactory,
    MaskPlaceholderFactory,
    RedactCounterPlaceholderFactory,
    RedactHashPlaceholderFactory,
    RedactPlaceholderFactory,
)
from piighost.resolver.entity import (
    DisabledEntityConflictResolver,
    FuzzyEntityConflictResolver,
    MergeEntityConflictResolver,
)
from piighost.resolver.span import (
    ConfidenceSpanConflictResolver,
    DisabledSpanConflictResolver,
)

if TYPE_CHECKING:
    from piighost.detector.base import AnyDetector
    from piighost.linker.entity import BaseEntityLinker
    from piighost.placeholder import AnyPlaceholderFactory
    from piighost.resolver.entity import AnyEntityConflictResolver
    from piighost.resolver.span import AnySpanConflictResolver


_DETECTOR_BUILDERS: dict[type[BaseModel], object] = {
    RegexDetectorConfig: RegexDetector,
    ChunkedDetectorConfig: "lazy:chunked",  # resolved lazily below
    Gliner2DetectorConfig: "lazy:gliner2",
    SpacyDetectorConfig: "lazy:spacy",
    TransformersDetectorConfig: "lazy:transformers",
    LLMDetectorConfig: "lazy:llm",
}


def _resolve_lazy_detector(key: str) -> type:
    """Lazy-import optional-dep detectors so ``piighost.config`` stays light."""
    if key == "lazy:gliner2":
        from piighost.detector.gliner2 import Gliner2Detector

        return Gliner2Detector
    if key == "lazy:spacy":
        from piighost.detector.spacy import SpacyDetector

        return SpacyDetector
    if key == "lazy:transformers":
        from piighost.detector.transformers import TransformersDetector

        return TransformersDetector
    if key == "lazy:llm":
        from piighost.detector.llm import LLMDetector

        return LLMDetector
    if key == "lazy:chunked":
        from piighost.detector.chunked import ChunkedDetector

        return ChunkedDetector
    raise KeyError(key)


def build_detector(cfg: BaseModel) -> "AnyDetector":
    builder = _DETECTOR_BUILDERS[type(cfg)]
    cls = builder if not isinstance(builder, str) else _resolve_lazy_detector(builder)
    return cls.from_config(cfg)  # pyrefly: ignore[missing-attribute]


_SPAN_RESOLVER_BUILDERS: dict[type[BaseModel], type] = {
    ConfidenceSpanResolverConfig: ConfidenceSpanConflictResolver,
    DisabledSpanResolverConfig: DisabledSpanConflictResolver,
}


def build_span_resolver(cfg: BaseModel) -> "AnySpanConflictResolver":
    return _SPAN_RESOLVER_BUILDERS[type(cfg)].from_config(cfg)


_LINKER_BUILDERS: dict[type[BaseModel], type] = {
    ExactEntityLinkerConfig: ExactEntityLinker,
    DisabledEntityLinkerConfig: DisabledEntityLinker,
}


def build_entity_linker(cfg: BaseModel) -> "BaseEntityLinker":
    return _LINKER_BUILDERS[type(cfg)].from_config(cfg)


_ENTITY_RESOLVER_BUILDERS: dict[type[BaseModel], type] = {
    MergeEntityResolverConfig: MergeEntityConflictResolver,
    FuzzyEntityResolverConfig: FuzzyEntityConflictResolver,
    DisabledEntityResolverConfig: DisabledEntityConflictResolver,
}


def build_entity_resolver(cfg: BaseModel) -> "AnyEntityConflictResolver":
    return _ENTITY_RESOLVER_BUILDERS[type(cfg)].from_config(cfg)


_PLACEHOLDER_BUILDERS: dict[type[BaseModel], object] = {
    LabelCounterPlaceholderConfig: LabelCounterPlaceholderFactory,
    LabelHashPlaceholderConfig: LabelHashPlaceholderFactory,
    LabelPlaceholderConfig: LabelPlaceholderFactory,
    MaskPlaceholderConfig: MaskPlaceholderFactory,
    RedactCounterPlaceholderConfig: RedactCounterPlaceholderFactory,
    RedactHashPlaceholderConfig: RedactHashPlaceholderFactory,
    RedactPlaceholderConfig: RedactPlaceholderFactory,
    FakerCounterPlaceholderConfig: "lazy:faker_counter",
    FakerHashPlaceholderConfig: "lazy:faker_hash",
    FakerPlaceholderConfig: "lazy:faker",
}


def _resolve_lazy_placeholder(key: str) -> type:
    """Lazy-import Faker-based factories so ``piighost.config`` stays importable without faker."""
    if key == "lazy:faker":
        from piighost.ph_factory.faker import FakerPlaceholderFactory

        return FakerPlaceholderFactory
    if key == "lazy:faker_counter":
        from piighost.ph_factory.faker_hash import FakerCounterPlaceholderFactory

        return FakerCounterPlaceholderFactory
    if key == "lazy:faker_hash":
        from piighost.ph_factory.faker_hash import FakerHashPlaceholderFactory

        return FakerHashPlaceholderFactory
    raise KeyError(key)


def build_placeholder_factory(cfg: BaseModel) -> "AnyPlaceholderFactory":
    builder = _PLACEHOLDER_BUILDERS[type(cfg)]
    cls = (
        builder if not isinstance(builder, str) else _resolve_lazy_placeholder(builder)
    )
    return cls.from_config(cfg)  # pyrefly: ignore[missing-attribute]


def build_anonymizer(cfg: DefaultAnonymizerConfig) -> Anonymizer:
    return Anonymizer.from_config(cfg)
