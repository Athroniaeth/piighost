"""Tests for the LabelHashPlaceholderFactory."""

from piighost.components.placeholder import (
    AnyPlaceholderFactory,
    LabelHashPlaceholderFactory,
)
from piighost.components.placeholder.tags import PreservesLabeledIdentityOpaque
from piighost.models import Detection, Entity, Span


def _entity(start: int, end: int, text: str, label: str = "PERSON") -> Entity:
    """Build a single-detection entity for the given text and label."""
    detection = Detection(span=Span(start, end), text=text, label=label, confidence=0.9)
    return Entity((detection,))


def _hash_part(token: str, label: str = "PERSON") -> str:
    """Return the digest between the <<LABEL: prefix and the >> suffix."""
    return token.removeprefix(f"<<{label}:").removesuffix(">>")


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """LabelHashPlaceholderFactory is an AnyPlaceholderFactory."""
        assert isinstance(LabelHashPlaceholderFactory(), AnyPlaceholderFactory)


class TestCreate:
    def test_token_names_the_label_and_a_hex_hash(self) -> None:
        """A token is <<LABEL:hash>> with a hex digest of the default length."""
        entity = _entity(0, 4, "Emma")
        token = LabelHashPlaceholderFactory().create([entity])[entity]
        digest = _hash_part(token)
        assert token.startswith("<<PERSON:") and token.endswith(">>")
        assert len(digest) == 8
        assert all(char in "0123456789abcdef" for char in digest)

    def test_token_depends_on_position_not_value(self) -> None:
        """The hash is of the ordinal, so a lone Emma and a lone Liam match."""
        emma = _entity(0, 4, "Emma")
        liam = _entity(0, 4, "Liam")
        factory = LabelHashPlaceholderFactory()
        assert factory.create([emma])[emma] == factory.create([liam])[liam]

    def test_entities_get_distinct_tokens_by_position(self) -> None:
        """Two entities of one label get different tokens from their ordinals."""
        emma = _entity(0, 4, "Emma")
        liam = _entity(9, 13, "Liam")
        tokens = LabelHashPlaceholderFactory().create([emma, liam])
        assert tokens[emma] != tokens[liam]

    def test_labels_do_not_collide(self) -> None:
        """The label is part of the digest, so PERSON:1 and EMAIL:1 differ."""
        person = _entity(0, 4, "Emma", label="PERSON")
        email = _entity(5, 20, "emma@mail.com", label="EMAIL")
        tokens = LabelHashPlaceholderFactory().create([person, email])
        assert tokens[person] != tokens[email]

    def test_hash_length_is_configurable(self) -> None:
        """The digest is truncated to the requested length."""
        entity = _entity(0, 4, "Emma")
        token = LabelHashPlaceholderFactory(hash_length=4).create([entity])[entity]
        assert len(_hash_part(token)) == 4

    def test_is_deterministic(self) -> None:
        """The same entity list yields the same tokens on every call."""
        factory = LabelHashPlaceholderFactory()
        entities = [_entity(0, 4, "Emma"), _entity(9, 13, "Liam")]
        assert factory.create(entities) == factory.create(entities)

    def test_no_entities_yields_no_tokens(self) -> None:
        """Creating tokens for nothing returns an empty mapping."""
        assert LabelHashPlaceholderFactory().create([]) == {}

    def test_tokens_carry_the_preservation_tag(self) -> None:
        """A token is an instance of the factory's tag, and still a plain str."""
        entity = _entity(0, 4, "Emma")
        token = LabelHashPlaceholderFactory().create([entity])[entity]
        assert isinstance(token, PreservesLabeledIdentityOpaque)
        assert isinstance(token, str)
