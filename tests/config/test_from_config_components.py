import pytest

from piighost.config.models.anonymizer import DefaultAnonymizerConfig
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
    LabelCounterPlaceholderConfig,
    MaskPlaceholderConfig,
)
from piighost.config.models.span_resolver import (
    ConfidenceSpanResolverConfig,
    DisabledSpanResolverConfig,
)
from piighost.anonymizer import Anonymizer
from piighost.linker.entity import ExactEntityLinker, DisabledEntityLinker
from piighost.placeholder import (
    LabelCounterPlaceholderFactory,
    MaskPlaceholderFactory,
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


def test_span_resolver_from_config_confidence():
    r = ConfidenceSpanConflictResolver.from_config(ConfidenceSpanResolverConfig())
    assert isinstance(r, ConfidenceSpanConflictResolver)


def test_span_resolver_from_config_disabled():
    r = DisabledSpanConflictResolver.from_config(
        DisabledSpanResolverConfig(type="disabled")
    )
    assert isinstance(r, DisabledSpanConflictResolver)


def test_entity_linker_from_config_exact():
    linker = ExactEntityLinker.from_config(ExactEntityLinkerConfig())
    assert isinstance(linker, ExactEntityLinker)


def test_entity_linker_from_config_disabled():
    linker = DisabledEntityLinker.from_config(
        DisabledEntityLinkerConfig(type="disabled")
    )
    assert isinstance(linker, DisabledEntityLinker)


def test_entity_resolver_from_config_merge():
    r = MergeEntityConflictResolver.from_config(MergeEntityResolverConfig())
    assert isinstance(r, MergeEntityConflictResolver)


def test_entity_resolver_from_config_fuzzy_threshold():
    cfg = FuzzyEntityResolverConfig(type="fuzzy", threshold=0.9)
    r = FuzzyEntityConflictResolver.from_config(cfg)
    assert isinstance(r, FuzzyEntityConflictResolver)
    assert r.threshold == 0.9


def test_entity_resolver_from_config_disabled():
    r = DisabledEntityConflictResolver.from_config(
        DisabledEntityResolverConfig(type="disabled")
    )
    assert isinstance(r, DisabledEntityConflictResolver)


def test_placeholder_factory_from_config_label_counter():
    f = LabelCounterPlaceholderFactory.from_config(LabelCounterPlaceholderConfig())
    assert isinstance(f, LabelCounterPlaceholderFactory)


def test_placeholder_factory_from_config_mask():
    f = MaskPlaceholderFactory.from_config(
        MaskPlaceholderConfig(type="mask", mask_char="#")
    )
    assert isinstance(f, MaskPlaceholderFactory)


@pytest.mark.skip(reason="depends on builders module, see Task 12")
def test_anonymizer_from_config_default():
    cfg = DefaultAnonymizerConfig(
        type="default",
        placeholder_factory=LabelCounterPlaceholderConfig(),
    )
    a = Anonymizer.from_config(cfg)
    assert isinstance(a, Anonymizer)
    assert isinstance(a.ph_factory, LabelCounterPlaceholderFactory)
