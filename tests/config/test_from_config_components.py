"""Config -> component construction via the ``build_*`` dispatchers.

These exercise the public construction path. Trivial components are
built generically by ``_construct`` (field-forwarding); transforming
ones (ExactEntityLinker, Anonymizer, Faker locale wrapping) keep a
custom ``from_config`` that the dispatcher invokes. Either way the
entry point is the same ``build_*`` function.
"""

from piighost.config.builders import (
    build_anonymizer,
    build_entity_linker,
    build_entity_resolver,
    build_placeholder_factory,
    build_span_resolver,
)
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
    FakerCounterPlaceholderConfig,
    FakerHashPlaceholderConfig,
    LabelCounterPlaceholderConfig,
    MaskPlaceholderConfig,
)
from piighost.config.models.span_resolver import (
    ConfidenceSpanResolverConfig,
    DisabledSpanResolverConfig,
)
from piighost.anonymizer import Anonymizer
from piighost.ph_factory.faker_hash import (
    FakerCounterPlaceholderFactory,
    FakerHashPlaceholderFactory,
)
from piighost.placeholder import (
    LabelCounterPlaceholderFactory,
    MaskPlaceholderFactory,
)
from piighost.linker.entity import ExactEntityLinker, DisabledEntityLinker
from piighost.resolver.entity import (
    DisabledEntityConflictResolver,
    FuzzyEntityConflictResolver,
    MergeEntityConflictResolver,
)
from piighost.resolver.span import (
    ConfidenceSpanConflictResolver,
    DisabledSpanConflictResolver,
)


def test_span_resolver_confidence():
    r = build_span_resolver(ConfidenceSpanResolverConfig())
    assert isinstance(r, ConfidenceSpanConflictResolver)


def test_span_resolver_disabled():
    r = build_span_resolver(DisabledSpanResolverConfig(type="disabled"))
    assert isinstance(r, DisabledSpanConflictResolver)


def test_entity_linker_exact():
    linker = build_entity_linker(ExactEntityLinkerConfig())
    assert isinstance(linker, ExactEntityLinker)


def test_entity_linker_disabled():
    linker = build_entity_linker(DisabledEntityLinkerConfig(type="disabled"))
    assert isinstance(linker, DisabledEntityLinker)


def test_entity_resolver_merge():
    r = build_entity_resolver(MergeEntityResolverConfig())
    assert isinstance(r, MergeEntityConflictResolver)


def test_entity_resolver_fuzzy_threshold():
    cfg = FuzzyEntityResolverConfig(type="fuzzy", threshold=0.9)
    r = build_entity_resolver(cfg)
    assert isinstance(r, FuzzyEntityConflictResolver)
    assert r.threshold == 0.9


def test_entity_resolver_disabled():
    r = build_entity_resolver(DisabledEntityResolverConfig(type="disabled"))
    assert isinstance(r, DisabledEntityConflictResolver)


def test_placeholder_factory_label_counter():
    f = build_placeholder_factory(LabelCounterPlaceholderConfig())
    assert isinstance(f, LabelCounterPlaceholderFactory)


def test_placeholder_factory_mask():
    f = build_placeholder_factory(MaskPlaceholderConfig(type="mask", mask_char="#"))
    assert isinstance(f, MaskPlaceholderFactory)


def test_faker_counter_default_locale():
    f = build_placeholder_factory(FakerCounterPlaceholderConfig(type="faker_counter"))
    assert isinstance(f, FakerCounterPlaceholderFactory)
    # Default locale is en_US — factory must be constructible.
    assert f._locale == "en_US"


def test_faker_counter_respects_locale():
    cfg = FakerCounterPlaceholderConfig(type="faker_counter", locale="fr_FR")
    f = build_placeholder_factory(cfg)
    assert isinstance(f, FakerCounterPlaceholderFactory)
    assert f._locale == "fr_FR"


def test_faker_hash_default_locale():
    f = build_placeholder_factory(FakerHashPlaceholderConfig(type="faker_hash"))
    assert isinstance(f, FakerHashPlaceholderFactory)
    assert f._locale == "en_US"


def test_faker_hash_respects_locale():
    cfg = FakerHashPlaceholderConfig(type="faker_hash", locale="fr_FR")
    f = build_placeholder_factory(cfg)
    assert isinstance(f, FakerHashPlaceholderFactory)
    assert f._locale == "fr_FR"


def test_anonymizer_default():
    cfg = DefaultAnonymizerConfig(
        type="default",
        placeholder_factory=LabelCounterPlaceholderConfig(),
    )
    a = build_anonymizer(cfg)
    assert isinstance(a, Anonymizer)
    assert isinstance(a.ph_factory, LabelCounterPlaceholderFactory)
