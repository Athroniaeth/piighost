"""Tests for the LabelCounterPlaceholderFactory."""

from piighost.components.placeholder import (
    AnyPlaceholderFactory,
    LabelCounterPlaceholderFactory,
)
from piighost.components.placeholder.tags import PreservesLabeledIdentityOpaque
from piighost.models import Detection, Entity, Span


def _entity(start: int, end: int, text: str, label: str = "PERSON") -> Entity:
    """Build a single-detection entity for the given text and label."""
    detection = Detection(span=Span(start, end), text=text, label=label, confidence=0.9)
    return Entity((detection,))


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """LabelCounterPlaceholderFactory is an AnyPlaceholderFactory."""
        assert isinstance(LabelCounterPlaceholderFactory(), AnyPlaceholderFactory)


class TestCreate:
    def test_numbers_entities_within_a_label(self) -> None:
        """Two entities of one label get consecutive numbers from one."""
        emma = _entity(0, 4, "Emma")
        liam = _entity(9, 13, "Liam")
        tokens = LabelCounterPlaceholderFactory().create([emma, liam])
        assert tokens == {emma: "<<PERSON:1>>", liam: "<<PERSON:2>>"}

    def test_each_label_counts_from_one(self) -> None:
        """A different label starts its own count rather than sharing one."""
        person = _entity(0, 4, "Emma", label="PERSON")
        email = _entity(5, 20, "emma@mail.com", label="EMAIL")
        tokens = LabelCounterPlaceholderFactory().create([person, email])
        assert tokens == {person: "<<PERSON:1>>", email: "<<EMAIL:1>>"}

    def test_distinct_entities_get_distinct_tokens(self) -> None:
        """Identity is preserved: no two entities share a token."""
        entities = [_entity(0, 4, "Emma"), _entity(9, 13, "Liam")]
        tokens = LabelCounterPlaceholderFactory().create(entities)
        assert len(set(tokens.values())) == len(entities)

    def test_is_deterministic(self) -> None:
        """The same entity list yields the same numbering on every call."""
        factory = LabelCounterPlaceholderFactory()
        entities = [_entity(0, 4, "Emma"), _entity(9, 13, "Liam")]
        assert factory.create(entities) == factory.create(entities)

    def test_no_entities_yields_no_tokens(self) -> None:
        """Creating tokens for nothing returns an empty mapping."""
        assert LabelCounterPlaceholderFactory().create([]) == {}

    def test_tokens_carry_the_preservation_tag(self) -> None:
        """A token is an instance of the factory's tag, and still a plain str."""
        entity = _entity(0, 4, "Emma")
        token = LabelCounterPlaceholderFactory().create([entity])[entity]
        assert isinstance(token, PreservesLabeledIdentityOpaque)
        assert isinstance(token, str)
