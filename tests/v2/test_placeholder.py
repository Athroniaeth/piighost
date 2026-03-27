"""Tests for placeholder factories."""

from v2.models import Detection, Entity, Span
from v2.placeholder import (
    CounterPlaceholderFactory,
    HashPlaceholderFactory,
    RedactPlaceholderFactory,
)


def _entity(text: str, label: str, start: int = 0) -> Entity:
    end = start + len(text)
    return Entity(
        detections=(
            Detection(
                text=text, label=label, position=Span(start, end), confidence=0.9
            ),
        )
    )


# ---------------------------------------------------------------------------
# CounterPlaceholderFactory
# ---------------------------------------------------------------------------


class TestCounterPlaceholderFactory:
    """Generates <<LABEL_N>> tokens with per-label counters."""

    def test_first_entity_gets_counter_one(self) -> None:
        e = _entity("Patrick", "PERSON")
        result = CounterPlaceholderFactory().create([e])
        assert result[e] == "<<PERSON_1>>"

    def test_second_entity_same_label_gets_counter_two(self) -> None:
        e1 = _entity("Patrick", "PERSON")
        e2 = _entity("Henri", "PERSON", start=20)
        result = CounterPlaceholderFactory().create([e1, e2])
        assert result[e1] == "<<PERSON_1>>"
        assert result[e2] == "<<PERSON_2>>"

    def test_different_labels_have_separate_counters(self) -> None:
        e1 = _entity("Patrick", "PERSON")
        e2 = _entity("Paris", "LOCATION")
        result = CounterPlaceholderFactory().create([e1, e2])
        assert result[e1] == "<<PERSON_1>>"
        assert result[e2] == "<<LOCATION_1>>"

    def test_empty_list(self) -> None:
        assert CounterPlaceholderFactory().create([]) == {}


# ---------------------------------------------------------------------------
# HashPlaceholderFactory
# ---------------------------------------------------------------------------


class TestHashPlaceholderFactory:
    """Generates <LABEL:hash> tokens using SHA-256."""

    def test_token_format(self) -> None:
        e = _entity("Patrick", "PERSON")
        token = HashPlaceholderFactory().create([e])[e]
        assert token.startswith("<PERSON:")
        assert token.endswith(">")

    def test_deterministic(self) -> None:
        e = _entity("Patrick", "PERSON")
        t1 = HashPlaceholderFactory().create([e])[e]
        t2 = HashPlaceholderFactory().create([e])[e]
        assert t1 == t2

    def test_different_entities_different_hashes(self) -> None:
        e1 = _entity("Patrick", "PERSON")
        e2 = _entity("Henri", "PERSON", start=20)
        result = HashPlaceholderFactory().create([e1, e2])
        assert result[e1] != result[e2]

    def test_same_text_different_label_different_hash(self) -> None:
        e1 = _entity("Paris", "LOCATION")
        e2 = _entity("Paris", "PERSON")
        result = HashPlaceholderFactory().create([e1, e2])
        assert result[e1] != result[e2]

    def test_custom_hash_length(self) -> None:
        e = _entity("Patrick", "PERSON")
        token = HashPlaceholderFactory(hash_length=4).create([e])[e]
        hash_part = token.split(":")[1].rstrip(">")
        assert len(hash_part) == 4

    def test_empty_list(self) -> None:
        assert HashPlaceholderFactory().create([]) == {}


# ---------------------------------------------------------------------------
# RedactPlaceholderFactory
# ---------------------------------------------------------------------------


class TestRedactPlaceholderFactory:
    """Generates <LABEL> tokens no discrimination between entities."""

    def test_token_format(self) -> None:
        e = _entity("Patrick", "PERSON")
        assert RedactPlaceholderFactory().create([e])[e] == "<PERSON>"

    def test_same_label_same_token(self) -> None:
        e1 = _entity("Patrick", "PERSON")
        e2 = _entity("Henri", "PERSON", start=20)
        result = RedactPlaceholderFactory().create([e1, e2])
        assert result[e1] == result[e2] == "<PERSON>"

    def test_different_labels_different_tokens(self) -> None:
        e1 = _entity("Patrick", "PERSON")
        e2 = _entity("Paris", "LOCATION")
        result = RedactPlaceholderFactory().create([e1, e2])
        assert result[e1] != result[e2]

    def test_empty_list(self) -> None:
        assert RedactPlaceholderFactory().create([]) == {}
