import pytest

from piighost.anonymizer import Anonymizer
from piighost.config.builders import (
    build_anonymizer,
    build_detector,
    build_entity_linker,
    build_entity_resolver,
    build_placeholder_factory,
    build_span_resolver,
)
from piighost.config.models.anonymizer import DefaultAnonymizerConfig
from piighost.config.models.detector import RegexDetectorConfig
from piighost.config.models.entity_linker import ExactEntityLinkerConfig
from piighost.config.models.entity_resolver import MergeEntityResolverConfig
from piighost.config.models.placeholder import LabelCounterPlaceholderConfig
from piighost.config.models.span_resolver import ConfidenceSpanResolverConfig
from piighost.detector.base import RegexDetector
from piighost.linker.entity import ExactEntityLinker
from piighost.placeholder import LabelCounterPlaceholderFactory
from piighost.resolver.entity import MergeEntityConflictResolver
from piighost.resolver.span import ConfidenceSpanConflictResolver


def test_build_detector_dispatch_on_config_type():
    cfg = RegexDetectorConfig(type="regex", patterns={"EMAIL": r"\S+@\S+"})
    d = build_detector(cfg)
    assert isinstance(d, RegexDetector)


def test_build_span_resolver_returns_confidence():
    r = build_span_resolver(ConfidenceSpanResolverConfig())
    assert isinstance(r, ConfidenceSpanConflictResolver)


def test_build_entity_linker_returns_exact():
    linker = build_entity_linker(ExactEntityLinkerConfig())
    assert isinstance(linker, ExactEntityLinker)


def test_build_entity_resolver_returns_merge():
    r = build_entity_resolver(MergeEntityResolverConfig())
    assert isinstance(r, MergeEntityConflictResolver)


def test_build_placeholder_factory_returns_label_counter():
    f = build_placeholder_factory(LabelCounterPlaceholderConfig())
    assert isinstance(f, LabelCounterPlaceholderFactory)


def test_build_anonymizer_includes_placeholder_factory():
    a = build_anonymizer(
        DefaultAnonymizerConfig(
            type="default",
            placeholder_factory=LabelCounterPlaceholderConfig(),
        )
    )
    assert isinstance(a, Anonymizer)
    assert isinstance(a.ph_factory, LabelCounterPlaceholderFactory)
