"""Tests for the optional-stage config models and the hash factory."""

import pytest
from pydantic import TypeAdapter, ValidationError

from piighost.components.entity_resolver import (
    FuzzyEntityResolver,
    MergeEntityResolver,
    SeparateEntityResolver,
)
from piighost.components.expander import WordBoundaryExpander
from piighost.components.overlap_resolver import ConfidenceOverlapResolver
from piighost.components.placeholder import LabelHashPlaceholderFactory
from piighost.config.models.entity_resolver import (
    EntityResolverConfig,
    FuzzyEntityResolverConfig,
    MergeEntityResolverConfig,
    SeparateEntityResolverConfig,
)
from piighost.config.models.expander import WordBoundaryExpanderConfig
from piighost.config.models.overlap_resolver import ConfidenceOverlapResolverConfig
from piighost.config.models.placeholder import LabelHashPlaceholderConfig
from piighost.models import Detection, Entity, Span


def _entity(text: str = "Emma", label: str = "PERSON") -> Entity:
    """Build a one-detection entity for a value and label."""
    detection = Detection(
        span=Span(0, len(text)), text=text, label=label, confidence=1.0
    )
    return Entity((detection,))


class TestOverlapResolverConfig:
    def test_builds_a_confidence_resolver(self) -> None:
        """The confidence config builds a ConfidenceOverlapResolver."""
        resolver = ConfidenceOverlapResolverConfig(type="confidence").build()
        assert isinstance(resolver, ConfidenceOverlapResolver)


class TestExpanderConfig:
    def test_builds_a_word_boundary_expander(self) -> None:
        """The word_boundary config builds a WordBoundaryExpander."""
        expander = WordBoundaryExpanderConfig(type="word_boundary").build()
        assert isinstance(expander, WordBoundaryExpander)

    def test_forwards_case_sensitive(self) -> None:
        """The config forwards case_sensitive to the expander."""
        expander = WordBoundaryExpanderConfig(
            type="word_boundary", case_sensitive=True
        ).build()
        assert expander.case_sensitive is True


class TestEntityResolverConfig:
    def test_merge_builds(self) -> None:
        """The merge config builds a MergeEntityResolver."""
        assert isinstance(
            MergeEntityResolverConfig(type="merge").build(), MergeEntityResolver
        )

    def test_separate_builds(self) -> None:
        """The separate config builds a SeparateEntityResolver."""
        resolver = SeparateEntityResolverConfig(type="separate").build()
        assert isinstance(resolver, SeparateEntityResolver)

    def test_fuzzy_builds_and_forwards_threshold(self) -> None:
        """The fuzzy config builds a FuzzyEntityResolver over its threshold."""
        resolver = FuzzyEntityResolverConfig(type="fuzzy", threshold=0.7).build()
        assert isinstance(resolver, FuzzyEntityResolver)
        assert resolver.threshold == 0.7

    def test_union_dispatches_on_type(self) -> None:
        """The type discriminant selects the matching resolver config."""
        adapter = TypeAdapter(EntityResolverConfig)
        parsed = adapter.validate_python({"type": "fuzzy", "threshold": 0.9})
        assert isinstance(parsed, FuzzyEntityResolverConfig)

    def test_rejects_out_of_range_threshold(self) -> None:
        """A threshold outside the zero to one range fails validation."""
        with pytest.raises(ValidationError):
            FuzzyEntityResolverConfig(type="fuzzy", threshold=1.5)


class TestLabelHashPlaceholderConfig:
    def test_builds_and_renders_a_hashed_token(self) -> None:
        """The label_hash config builds a factory rendering a hashed token."""
        factory = LabelHashPlaceholderConfig(type="label_hash", hash_length=8).build()
        assert isinstance(factory, LabelHashPlaceholderFactory)
        entities = [_entity()]
        token = factory.create(entities)[entities[0]]
        assert token.startswith("<<PERSON:")
        assert token.endswith(">>")

    def test_rejects_zero_hash_length(self) -> None:
        """A zero hash_length fails validation, it would render an empty digest."""
        with pytest.raises(ValidationError):
            LabelHashPlaceholderConfig(type="label_hash", hash_length=0)
