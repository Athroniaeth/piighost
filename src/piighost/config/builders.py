"""Type-mapping factories for ``piighost.config``.

Each ``build_*`` function dispatches on the concrete config class
(which Pydantic has already discriminated) to the matching component
class's ``from_config`` classmethod. Mappings are plain ``dict``s
keyed on the config type so dispatch is O(1) and trivially auditable.

Imports of the GLiNER / spaCy / transformers / LLM detector classes
are deferred to inside ``build_detector`` to keep ``piighost.config``
importable without their optional dependencies installed.
"""

import importlib
import os
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel

from piighost.anonymizer import Anonymizer
from piighost.config.models.anonymizer import DefaultAnonymizerConfig
from piighost.config.models.cache import (
    MemoryCacheConfig,
    RedisCacheConfig,
    SqlAlchemyCacheConfig,
)
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
    from aiocache.base import BaseCache

    from piighost.detector.base import AnyDetector
    from piighost.linker.entity import BaseEntityLinker
    from piighost.placeholder import AnyPlaceholderFactory
    from piighost.resolver.entity import AnyEntityConflictResolver
    from piighost.resolver.span import AnySpanConflictResolver


_COMMON_CONFIG_FIELDS = {"type", "name"}
"""Config fields that are never constructor parameters (discriminator + label)."""


def _construct(cls: Any, cfg: BaseModel) -> Any:
    """Instantiate a component from its validated config.

    Uses the class's own ``from_config`` when it defines one *directly*
    (needed when construction transforms fields or loads a resource).
    Otherwise builds generically by forwarding the config fields as
    keyword arguments, which covers every component whose config field
    names match its constructor parameters.

    Typed ``Any`` because this is a dynamic dispatcher: the component
    classes do not share a ``from_config`` protocol, and the generic
    branch constructs an arbitrary class. The concrete ``build_*``
    wrappers re-narrow the return to the family's protocol type.
    """
    if "from_config" in cls.__dict__:
        return cls.from_config(cfg)
    return cls(**cfg.model_dump(exclude=_COMMON_CONFIG_FIELDS))


_DETECTOR_BUILDERS: dict[type[BaseModel], object] = {
    RegexDetectorConfig: RegexDetector,
    ChunkedDetectorConfig: "lazy:chunked",  # resolved lazily below
    Gliner2DetectorConfig: "lazy:gliner2",
    SpacyDetectorConfig: "lazy:spacy",
    TransformersDetectorConfig: "lazy:transformers",
    LLMDetectorConfig: "lazy:llm",
}


# Sentinel -> (module path, class name). Resolved one at a time via
# ``importlib`` so importing ``piighost.config`` never pulls an optional
# dependency that the requested detector does not need.
_LAZY_DETECTORS: dict[str, tuple[str, str]] = {
    "lazy:gliner2": ("piighost.detector.gliner2", "Gliner2Detector"),
    "lazy:spacy": ("piighost.detector.spacy", "SpacyDetector"),
    "lazy:transformers": ("piighost.detector.transformers", "TransformersDetector"),
    "lazy:llm": ("piighost.detector.llm", "LLMDetector"),
    "lazy:chunked": ("piighost.detector.chunked", "ChunkedDetector"),
}


def _resolve_lazy_detector(key: str) -> type:
    """Lazy-import optional-dep detectors so ``piighost.config`` stays light."""
    module_path, class_name = _LAZY_DETECTORS[key]
    return getattr(importlib.import_module(module_path), class_name)


def build_detector(cfg: BaseModel) -> "AnyDetector":
    builder = _DETECTOR_BUILDERS[type(cfg)]
    cls = builder if not isinstance(builder, str) else _resolve_lazy_detector(builder)
    return _construct(cls, cfg)


_SPAN_RESOLVER_BUILDERS: dict[type[BaseModel], type] = {
    ConfidenceSpanResolverConfig: ConfidenceSpanConflictResolver,
    DisabledSpanResolverConfig: DisabledSpanConflictResolver,
}


def build_span_resolver(cfg: BaseModel) -> "AnySpanConflictResolver":
    return _construct(_SPAN_RESOLVER_BUILDERS[type(cfg)], cfg)


_LINKER_BUILDERS: dict[type[BaseModel], type] = {
    ExactEntityLinkerConfig: ExactEntityLinker,
    DisabledEntityLinkerConfig: DisabledEntityLinker,
}


def build_entity_linker(cfg: BaseModel) -> "BaseEntityLinker":
    return _construct(_LINKER_BUILDERS[type(cfg)], cfg)


_ENTITY_RESOLVER_BUILDERS: dict[type[BaseModel], type] = {
    MergeEntityResolverConfig: MergeEntityConflictResolver,
    FuzzyEntityResolverConfig: FuzzyEntityConflictResolver,
    DisabledEntityResolverConfig: DisabledEntityConflictResolver,
}


def build_entity_resolver(cfg: BaseModel) -> "AnyEntityConflictResolver":
    return _construct(_ENTITY_RESOLVER_BUILDERS[type(cfg)], cfg)


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


# Sentinel -> (module path, class name); see ``_LAZY_DETECTORS``.
_LAZY_PLACEHOLDERS: dict[str, tuple[str, str]] = {
    "lazy:faker": ("piighost.ph_factory.faker", "FakerPlaceholderFactory"),
    "lazy:faker_counter": (
        "piighost.ph_factory.faker_hash",
        "FakerCounterPlaceholderFactory",
    ),
    "lazy:faker_hash": (
        "piighost.ph_factory.faker_hash",
        "FakerHashPlaceholderFactory",
    ),
}


def _resolve_lazy_placeholder(key: str) -> type:
    """Lazy-import Faker-based factories so ``piighost.config`` stays importable without faker."""
    module_path, class_name = _LAZY_PLACEHOLDERS[key]
    return getattr(importlib.import_module(module_path), class_name)


def build_placeholder_factory(cfg: BaseModel) -> "AnyPlaceholderFactory":
    builder = _PLACEHOLDER_BUILDERS[type(cfg)]
    cls = (
        builder if not isinstance(builder, str) else _resolve_lazy_placeholder(builder)
    )
    return _construct(cls, cfg)


def build_anonymizer(cfg: DefaultAnonymizerConfig) -> Anonymizer:
    return Anonymizer.from_config(cfg)


def build_cache(cfg: BaseModel) -> "BaseCache":
    """Build the cache backend from its validated configuration.

    URL-bearing backends read their connection URL from the environment
    variable named by ``url_env`` and raise ``ConfigError`` when it is
    unset, so a misconfigured deployment fails at startup instead of
    silently degrading to a process-local cache.
    """
    from piighost.config.errors import ConfigError

    if isinstance(cfg, MemoryCacheConfig):
        from aiocache import SimpleMemoryCache

        return SimpleMemoryCache()

    if not isinstance(cfg, (RedisCacheConfig, SqlAlchemyCacheConfig)):
        raise ConfigError(f"unknown cache type: {type(cfg).__name__!r}")

    url = os.environ.get(cfg.url_env)
    if not url:
        raise ConfigError(
            f"[cache] type={cfg.type!r} requires the {cfg.url_env!r} "
            f"environment variable to hold the connection URL"
        )
    if isinstance(cfg, RedisCacheConfig):
        from aiocache import Cache

        try:
            return cast("BaseCache", Cache.from_url(url))
        except Exception as exc:
            raise ConfigError(
                f"[cache] type='redis' could not build the backend from "
                f"{cfg.url_env}={url!r}: {exc}. If the redis driver is "
                f"missing, install the extra: piighost[redis]."
            ) from exc

    from piighost.cache.sqlalchemy import SQLAlchemyCache

    return SQLAlchemyCache(url=url, table_name=cfg.table_name)
