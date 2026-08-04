"""Tests for the config component models and their build()."""

import pytest
from pydantic import ValidationError

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import CompositeDetector, RegexDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import (
    LabelCounterPlaceholderFactory,
    LabelPlaceholderFactory,
    MaskPlaceholderFactory,
    RedactPlaceholderFactory,
)
from piighost.config.models.anonymizer import AnonymizerConfig
from piighost.config.models.detector import (
    CompositeDetectorConfig,
    DetectorConfig,
    RegexDetectorConfig,
)
from piighost.config.models.linker import ExactLinkerConfig
from piighost.config.models.placeholder import (
    LabelCounterPlaceholderConfig,
    LabelPlaceholderConfig,
    MaskPlaceholderConfig,
    RedactPlaceholderConfig,
)
from piighost.models import Detection, Entity, Span


def _entity(text: str = "Emma", label: str = "PERSON") -> Entity:
    """Build a one-detection entity for a value and label."""
    detection = Detection(
        span=Span(0, len(text)), text=text, label=label, confidence=1.0
    )
    return Entity((detection,))


class TestDetectorConfig:
    def test_regex_builds_a_regex_detector(self) -> None:
        """A regex config builds a RegexDetector over its patterns."""
        config = RegexDetectorConfig(type="regex", patterns={"EMAIL": "a@b"})
        detector = config.build()
        assert isinstance(detector, RegexDetector)
        assert detector.patterns == {"EMAIL": "a@b"}

    def test_composite_builds_from_nested_detectors(self) -> None:
        """A composite config builds a CompositeDetector from its children."""
        config = CompositeDetectorConfig(
            type="composite",
            detectors=[RegexDetectorConfig(type="regex", patterns={"A": "a"})],
        )
        detector = config.build()
        assert isinstance(detector, CompositeDetector)

    def test_unknown_key_is_rejected(self) -> None:
        """A model forbids keys it does not declare, catching typos."""
        with pytest.raises(ValidationError):
            RegexDetectorConfig(type="regex", patterns={"A": "a"}, nope=1)


class TestPlaceholderConfig:
    def test_each_factory_builds_and_renders(self) -> None:
        """Each core factory config builds a factory rendering its token."""
        entities = [_entity()]
        redact = RedactPlaceholderConfig(type="redact").build()
        label = LabelPlaceholderConfig(type="label").build()
        counter = LabelCounterPlaceholderConfig(type="label_counter").build()
        mask = MaskPlaceholderConfig(type="mask").build()
        assert isinstance(redact, RedactPlaceholderFactory)
        assert isinstance(label, LabelPlaceholderFactory)
        assert isinstance(counter, LabelCounterPlaceholderFactory)
        assert isinstance(mask, MaskPlaceholderFactory)
        assert redact.create(entities)[entities[0]] == "<<REDACT>>"
        assert label.create(entities)[entities[0]] == "<<PERSON>>"
        assert counter.create(entities)[entities[0]] == "<<PERSON:1>>"
        assert mask.create(entities)[entities[0]] == "E***"

    def test_mask_carries_its_options(self) -> None:
        """The mask config forwards visible and mask_char to the factory."""
        factory = MaskPlaceholderConfig(type="mask", visible=2, mask_char="#").build()
        entities = [_entity(text="Emma")]
        assert factory.create(entities)[entities[0]] == "Em##"


class TestLinkerAndAnonymizerConfig:
    def test_exact_linker_builds(self) -> None:
        """The linker config builds an ExactEntityLinker."""
        assert isinstance(ExactLinkerConfig(type="exact").build(), ExactEntityLinker)

    def test_anonymizer_builds_on_its_placeholder(self) -> None:
        """The anonymizer config builds an Anonymizer on its factory."""
        config = AnonymizerConfig(placeholder=RedactPlaceholderConfig(type="redact"))
        anonymizer = config.build()
        assert isinstance(anonymizer, Anonymizer)
        assert isinstance(anonymizer.factory, RedactPlaceholderFactory)


class TestDiscriminatedUnion:
    def test_type_selects_the_model(self) -> None:
        """The type discriminant parses to the matching concrete model."""
        from pydantic import TypeAdapter

        adapter = TypeAdapter(DetectorConfig)
        parsed = adapter.validate_python({"type": "regex", "patterns": {"A": "a"}})
        assert isinstance(parsed, RegexDetectorConfig)
