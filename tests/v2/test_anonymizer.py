"""Tests for ``Anonymizer``."""

from v2.anonymizer import Anonymizer
from v2.models import Detection, Entity, Span
from v2.placeholder import (
    CounterPlaceholderFactory,
    HashPlaceholderFactory,
    RedactPlaceholderFactory,
)


def _det(
    text: str, label: str, start: int, end: int, confidence: float = 0.9
) -> Detection:
    return Detection(
        text=text, label=label, position=Span(start, end), confidence=confidence
    )


# ---------------------------------------------------------------------------
# Anonymize
# ---------------------------------------------------------------------------


class TestAnonymize:
    """anonymize() replaces detections with tokens."""

    def test_single_entity_single_detection(self) -> None:
        entities = [Entity(detections=(_det("Patrick", "PERSON", 0, 7),))]
        result = Anonymizer(CounterPlaceholderFactory()).anonymize(
            "Patrick est gentil",
            entities,
        )
        assert result == "<<PERSON_1>> est gentil"

    def test_single_entity_multiple_detections(self) -> None:
        entities = [
            Entity(
                detections=(
                    _det("Patrick", "PERSON", 0, 7),
                    _det("Patrick", "PERSON", 20, 27),
                )
            )
        ]
        text = "Patrick est gentil. Patrick habite ici."
        result = Anonymizer(CounterPlaceholderFactory()).anonymize(text, entities)
        assert result == "<<PERSON_1>> est gentil. <<PERSON_1>> habite ici."

    def test_multiple_entities(self) -> None:
        entities = [
            Entity(detections=(_det("Patrick", "PERSON", 0, 7),)),
            Entity(detections=(_det("Paris", "LOCATION", 17, 22),)),
        ]
        result = Anonymizer(CounterPlaceholderFactory()).anonymize(
            "Patrick habite à Paris",
            entities,
        )
        assert "<<PERSON_1>>" in result
        assert "<<LOCATION_1>>" in result
        assert "Patrick" not in result
        assert "Paris" not in result

    def test_no_entities_returns_unchanged(self) -> None:
        result = Anonymizer(CounterPlaceholderFactory()).anonymize("Hello world", [])
        assert result == "Hello world"

    def test_with_hash_factory(self) -> None:
        entities = [Entity(detections=(_det("Patrick", "PERSON", 0, 7),))]
        result = Anonymizer(HashPlaceholderFactory()).anonymize(
            "Patrick est gentil",
            entities,
        )
        assert result.startswith("<PERSON:")
        assert "Patrick" not in result

    def test_with_redact_factory(self) -> None:
        entities = [
            Entity(detections=(_det("Patrick", "PERSON", 0, 7),)),
            Entity(detections=(_det("Henri", "PERSON", 11, 16),)),
        ]
        result = Anonymizer(RedactPlaceholderFactory()).anonymize(
            "Patrick et Henri sont amis",
            entities,
        )
        assert result == "<PERSON> et <PERSON> sont amis"


# ---------------------------------------------------------------------------
# Deanonymize
# ---------------------------------------------------------------------------


class TestDeanonymize:
    """deanonymize() restores the original text."""

    def test_roundtrip_single_entity(self) -> None:
        entities = [Entity(detections=(_det("Patrick", "PERSON", 0, 7),))]
        text = "Patrick est gentil"
        anon = Anonymizer(CounterPlaceholderFactory())
        anonymized = anon.anonymize(text, entities)
        restored = anon.deanonymize(anonymized, entities)
        assert restored == text

    def test_roundtrip_multiple_entities(self) -> None:
        entities = [
            Entity(detections=(_det("Patrick", "PERSON", 0, 7),)),
            Entity(detections=(_det("Paris", "LOCATION", 17, 22),)),
        ]
        text = "Patrick habite à Paris"
        anon = Anonymizer(CounterPlaceholderFactory())
        anonymized = anon.anonymize(text, entities)
        restored = anon.deanonymize(anonymized, entities)
        assert restored == text

    def test_roundtrip_multiple_detections(self) -> None:
        entities = [
            Entity(
                detections=(
                    _det("Patrick", "PERSON", 0, 7),
                    _det("Patrick", "PERSON", 20, 27),
                )
            )
        ]
        text = "Patrick est gentil. Patrick habite ici."
        ph_factory = CounterPlaceholderFactory()
        anon = Anonymizer(ph_factory=ph_factory)
        anonymized = anon.anonymize(text, entities)
        assert anonymized == "<<PERSON_1>> est gentil. <<PERSON_1>> habite ici."

        restored = anon.deanonymize(anonymized, entities)
        assert restored == text

    def test_roundtrip_spelling_variants(self) -> None:
        # Same entity but different spellings both must be restored correctly.
        entities = [
            Entity(
                detections=(
                    _det("Patrick", "PERSON", 0, 7),
                    _det("patric", "PERSON", 20, 26),
                )
            )
        ]
        text = "Patrick est gentil. patric habite ici."
        ph_factory = CounterPlaceholderFactory()
        anon = Anonymizer(ph_factory=ph_factory)

        anonymized = anon.anonymize(text, entities)
        assert anonymized.count("<<PERSON_1>>") == 2

        restored = anon.deanonymize(anonymized, entities)
        assert restored == text

    def test_roundtrip_with_redact(self) -> None:
        entities = [Entity(detections=(_det("Patrick", "PERSON", 0, 7),))]
        text = "Patrick est gentil"
        ph_factory = RedactPlaceholderFactory()
        anon = Anonymizer(ph_factory=ph_factory)

        anonymized = anon.anonymize(text, entities)
        assert anonymized == "<PERSON> est gentil"

        restored = anon.deanonymize(anonymized, entities)
        assert restored == text

    def test_roundtrip_redact_multiple_same_label(self) -> None:
        entities = [
            Entity(detections=(_det("Patrick", "PERSON", 0, 7),)),
            Entity(detections=(_det("Henri", "PERSON", 11, 16),)),
        ]
        text = "Patrick et Henri sont amis"
        ph_factory = RedactPlaceholderFactory()
        anon = Anonymizer(ph_factory=ph_factory)
        anonymized = anon.anonymize(text, entities)
        restored = anon.deanonymize(anonymized, entities)
        assert restored == text

    def test_roundtrip_with_hash(self) -> None:
        entities = [Entity(detections=(_det("Patrick", "PERSON", 0, 7),))]
        text = "Patrick est gentil"
        ph_factory = HashPlaceholderFactory()
        anon = Anonymizer(ph_factory=ph_factory)
        anonymized = anon.anonymize(text, entities)
        restored = anon.deanonymize(anonymized, entities)
        assert restored == text
