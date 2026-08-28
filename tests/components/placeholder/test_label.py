"""Tests for the LabelPlaceholderFactory."""

from piighost.components.placeholder import (
    AnyPlaceholderFactory,
    LabelPlaceholderFactory,
)
from piighost.components.placeholder.tags import PreservesLabel
from piighost.models import Detection, Entity, Span


def _entity(start: int, end: int, text: str, label: str = "PERSON") -> Entity:
    """Build a single-detection entity for the given text and label."""
    detection = Detection(span=Span(start, end), text=text, label=label, confidence=0.9)
    return Entity((detection,))


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """LabelPlaceholderFactory is an AnyPlaceholderFactory."""
        assert isinstance(LabelPlaceholderFactory(), AnyPlaceholderFactory)


class TestCreate:
    def test_names_the_label_in_the_token(self) -> None:
        """An entity becomes an angle-bracketed form of its label."""
        person = _entity(0, 4, "Emma", label="PERSON")
        assert LabelPlaceholderFactory().create([person]) == {person: "<<PERSON>>"}

    def test_same_label_collapses_to_one_token(self) -> None:
        """Two entities sharing a label get the same token, losing identity."""
        emma = _entity(0, 4, "Emma", label="PERSON")
        liam = _entity(9, 13, "Liam", label="PERSON")
        tokens = LabelPlaceholderFactory().create([emma, liam])
        assert tokens[emma] == tokens[liam] == "<<PERSON>>"

    def test_different_labels_get_different_tokens(self) -> None:
        """Entities of distinct labels get distinct tokens."""
        person = _entity(0, 4, "Emma", label="PERSON")
        email = _entity(5, 20, "emma@mail.com", label="EMAIL")
        tokens = LabelPlaceholderFactory().create([person, email])
        assert tokens[person] == "<<PERSON>>"
        assert tokens[email] == "<<EMAIL>>"

    def test_is_deterministic(self) -> None:
        """The same entities yield the same mapping on every call."""
        factory = LabelPlaceholderFactory()
        entities = [_entity(0, 4, "Emma"), _entity(9, 13, "Liam")]
        assert factory.create(entities) == factory.create(entities)

    def test_no_entities_yields_no_tokens(self) -> None:
        """Creating tokens for nothing returns an empty mapping."""
        assert LabelPlaceholderFactory().create([]) == {}

    def test_tokens_carry_the_preservation_tag(self) -> None:
        """A token is an instance of the factory's tag, and still a plain str."""
        entity = _entity(0, 4, "Emma")
        token = LabelPlaceholderFactory().create([entity])[entity]
        assert isinstance(token, PreservesLabel)
        assert isinstance(token, str)
