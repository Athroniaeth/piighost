"""Tests for the RedactPlaceholderFactory."""

from piighost.models import Detection, Entity, Span
from piighost.components.placeholder import (
    AnyPlaceholderFactory,
    RedactPlaceholderFactory,
)
from piighost.components.placeholder.tags import PreservesNothing

REDACT_TOKEN = PreservesNothing("<<REDACT>>")
"""The default redaction token, rebuilt here to assert the mapping."""


def _entity(start: int, end: int, text: str, label: str = "PERSON") -> Entity:
    """Build a single-detection entity for the given text and label."""
    detection = Detection(span=Span(start, end), text=text, label=label, confidence=0.9)
    return Entity((detection,))


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """RedactPlaceholderFactory is an AnyPlaceholderFactory."""
        assert isinstance(RedactPlaceholderFactory(), AnyPlaceholderFactory)


class TestCreate:
    def test_maps_every_entity_to_the_redact_token(self) -> None:
        """Each entity, whatever its value or label, collapses to one token."""
        person = _entity(0, 4, "Emma", label="PERSON")
        email = _entity(5, 20, "emma@mail.com", label="EMAIL")
        tokens = RedactPlaceholderFactory().create([person, email])
        assert tokens == {person: REDACT_TOKEN, email: REDACT_TOKEN}

    def test_is_deterministic(self) -> None:
        """The same entities yield the same mapping on every call."""
        factory = RedactPlaceholderFactory()
        entities = [_entity(0, 4, "Emma"), _entity(9, 13, "Liam")]
        assert factory.create(entities) == factory.create(entities)

    def test_no_entities_yields_no_tokens(self) -> None:
        """Creating tokens for nothing returns an empty mapping."""
        assert RedactPlaceholderFactory().create([]) == {}

    def test_tokens_carry_the_preservation_tag(self) -> None:
        """A token is an instance of the factory's tag, and still a plain str."""
        entity = _entity(0, 4, "Emma")
        token = RedactPlaceholderFactory().create([entity])[entity]
        assert isinstance(token, PreservesNothing)
        assert isinstance(token, str)
