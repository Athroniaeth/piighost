"""Tests for the span-replacement Anonymizer."""

from piighost.anonymizer import Anonymizer, AnyAnonymizer
from piighost.models import Detection, Entity, Span
from piighost.placeholder import (
    LabelCounterPlaceholderFactory,
    RedactPlaceholderFactory,
)


def _detection(start: int, end: int, text: str, label: str = "PERSON") -> Detection:
    """Build a detection covering [start, end) for the given text and label."""
    return Detection(span=Span(start, end), text=text, label=label, confidence=0.9)


def _entity(spans: list[tuple[int, int]], text: str, label: str = "PERSON") -> Entity:
    """Build an entity grouping one detection per span."""
    return Entity(tuple(_detection(start, end, text, label) for start, end in spans))


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """Anonymizer is an AnyAnonymizer."""
        assert isinstance(Anonymizer(RedactPlaceholderFactory()), AnyAnonymizer)


class TestAnonymize:
    def test_replaces_a_single_occurrence(self) -> None:
        """One entity occurrence is swapped for its token, the rest kept."""
        emma = _entity([(5, 9)], "Emma")
        result = Anonymizer(RedactPlaceholderFactory()).anonymize("I am Emma", [emma])
        assert result.text == "I am <<REDACT>>"

    def test_replaces_every_occurrence_of_one_entity(self) -> None:
        """All spans of an entity get the same token."""
        emma = _entity([(0, 4), (9, 13)], "Emma")
        result = Anonymizer(RedactPlaceholderFactory()).anonymize("Emma and Emma", [emma])
        assert result.text == "<<REDACT>> and <<REDACT>>"

    def test_replaces_several_entities(self) -> None:
        """Distinct entities each get their own token, interleaved correctly."""
        emma = _entity([(0, 4), (15, 19)], "Emma")
        liam = _entity([(9, 13)], "Liam")
        anonymizer = Anonymizer(LabelCounterPlaceholderFactory())
        result = anonymizer.anonymize("Emma met Liam. Emma left.", [emma, liam])
        assert result.text == "<<PERSON:1>> met <<PERSON:2>>. <<PERSON:1>> left."

    def test_result_carries_the_token_of_each_entity(self) -> None:
        """The result exposes the token every entity was replaced with."""
        emma = _entity([(0, 4)], "Emma")
        liam = _entity([(9, 13)], "Liam")
        result = Anonymizer(LabelCounterPlaceholderFactory()).anonymize(
            "Emma and Liam", [emma, liam]
        )
        assert result.tokens == {emma: "<<PERSON:1>>", liam: "<<PERSON:2>>"}

    def test_no_entities_leaves_the_text_unchanged(self) -> None:
        """With nothing to replace, the text passes through and tokens are empty."""
        result = Anonymizer(RedactPlaceholderFactory()).anonymize("nothing here", [])
        assert result.text == "nothing here"
        assert result.tokens == {}


class TestDeanonymize:
    def test_restores_a_single_token(self) -> None:
        """A token in the text is swapped back for its entity's value."""
        emma = _entity([(0, 4)], "Emma")
        anonymizer = Anonymizer(LabelCounterPlaceholderFactory())
        tokens = anonymizer.anonymize("Emma", [emma]).tokens
        assert anonymizer.deanonymize("Hello <<PERSON:1>>", tokens) == "Hello Emma"

    def test_restores_a_novel_text(self) -> None:
        """A text the pipeline never produced still has its tokens restored."""
        emma = _entity([(0, 4)], "Emma")
        anonymizer = Anonymizer(LabelCounterPlaceholderFactory())
        tokens = anonymizer.anonymize("Emma", [emma]).tokens
        assert anonymizer.deanonymize("Sure, <<PERSON:1>>!", tokens) == "Sure, Emma!"

    def test_restores_every_occurrence(self) -> None:
        """Every occurrence of a token is restored, not just the first."""
        emma = _entity([(0, 4)], "Emma")
        anonymizer = Anonymizer(LabelCounterPlaceholderFactory())
        tokens = anonymizer.anonymize("Emma", [emma]).tokens
        result = anonymizer.deanonymize("<<PERSON:1>> and <<PERSON:1>>", tokens)
        assert result == "Emma and Emma"

    def test_restores_several_entities(self) -> None:
        """Each token maps back to its own entity's value."""
        emma = _entity([(0, 4)], "Emma")
        liam = _entity([(9, 13)], "Liam")
        anonymizer = Anonymizer(LabelCounterPlaceholderFactory())
        tokens = anonymizer.anonymize("Emma and Liam", [emma, liam]).tokens
        result = anonymizer.deanonymize("<<PERSON:2>> then <<PERSON:1>>", tokens)
        assert result == "Liam then Emma"

    def test_unknown_token_passes_through(self) -> None:
        """A token absent from the mapping is left untouched."""
        emma = _entity([(0, 4)], "Emma")
        anonymizer = Anonymizer(LabelCounterPlaceholderFactory())
        tokens = anonymizer.anonymize("Emma", [emma]).tokens
        assert anonymizer.deanonymize("<<PERSON:9>>", tokens) == "<<PERSON:9>>"

    def test_no_tokens_leaves_text_unchanged(self) -> None:
        """With an empty mapping the text passes through untouched."""
        anonymizer = Anonymizer(LabelCounterPlaceholderFactory())
        assert anonymizer.deanonymize("nothing here", {}) == "nothing here"

    def test_roundtrip_restores_the_original(self) -> None:
        """Anonymizing then deanonymizing the result returns the original text."""
        emma = _entity([(0, 4)], "Emma")
        liam = _entity([(9, 13)], "Liam")
        anonymizer = Anonymizer(LabelCounterPlaceholderFactory())
        result = anonymizer.anonymize("Emma met Liam", [emma, liam])
        assert anonymizer.deanonymize(result.text, result.tokens) == "Emma met Liam"
