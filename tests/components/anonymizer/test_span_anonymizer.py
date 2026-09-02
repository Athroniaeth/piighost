"""Tests for the span-replacement Anonymizer."""

import pytest

from piighost.components.anonymizer import Anonymizer, AnyAnonymizer
from piighost.components.placeholder import (
    LabelCounterPlaceholderFactory,
    RedactPlaceholderFactory,
)
from piighost.exceptions import OverlappingSpansError
from piighost.models import Detection, Entity, Span


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
        result = Anonymizer(RedactPlaceholderFactory()).anonymize(
            "Emma and Emma", [emma]
        )
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

    def test_user_typed_token_cannot_hijack_a_restore(self) -> None:
        """A token a user typed is neutralized, so it cannot leak another value.

        Without this, a user who writes <<PERSON:2>> would see it restored to the
        second entity's value at deanonymization, an injection vector.
        """
        anonymizer = Anonymizer(LabelCounterPlaceholderFactory())
        emma = _entity([(0, 4)], "Emma")
        bob = _entity([(24, 27)], "Bob")
        text = "Emma wrote <<PERSON:2>> Bob"
        result = anonymizer.anonymize(text, [emma, bob])
        # Only Bob's real token remains; the typed one is broken.
        assert result.text.count("<<PERSON:2>>") == 1
        restored = anonymizer.deanonymize(result.text, result.tokens)
        assert restored.count("Bob") == 1

    def test_escaping_can_be_disabled(self) -> None:
        """With escaping off, a typed token is left intact (opt-out)."""
        anonymizer = Anonymizer(
            LabelCounterPlaceholderFactory(), escape_existing_tokens=False
        )
        emma = _entity([(0, 4)], "Emma")
        bob = _entity([(24, 27)], "Bob")
        text = "Emma wrote <<PERSON:2>> Bob"
        result = anonymizer.anonymize(text, [emma, bob])
        assert result.text.count("<<PERSON:2>>") == 2

    def test_overlapping_spans_raise(self) -> None:
        """Overlapping entity spans fail closed rather than corrupt the text.

        The render loop assumes disjoint spans (the overlap-resolver stage cleans
        them upstream). If two spans overlap here it raises instead of splicing a
        clear fragment of one detection into the middle of another.
        """
        first = _entity([(0, 8)], "Patrick", "PERSON")
        second = _entity([(4, 12)], "Dupont", "COMPANY")
        anonymizer = Anonymizer(LabelCounterPlaceholderFactory())
        with pytest.raises(OverlappingSpansError):
            anonymizer.anonymize("Patrick Dupont xx", [first, second])


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

    def test_no_prefix_collision_when_one_token_prefixes_another(self) -> None:
        """A token that prefixes another (e.g. [PERSON:1 vs [PERSON:10) is safe.

        With an empty suffix, sequential replacement of [PERSON:1 would corrupt
        [PERSON:10 and [PERSON:11. The longest match must win, in one pass.
        """
        factory = LabelCounterPlaceholderFactory(prefix="[", suffix="")
        anonymizer = Anonymizer(factory)
        entities = [_entity([(i, i + 1)], f"VALUE_{i}_END") for i in range(1, 12)]
        tokens = anonymizer.create(entities)
        text = " ".join(str(tokens[entity]) for entity in entities)
        restored = anonymizer.deanonymize(text, tokens)
        assert restored == " ".join(entity.text for entity in entities)

    def test_restored_value_holding_a_token_is_not_resubstituted(self) -> None:
        """A restored value that itself looks like a token is left as is.

        Restoration is one pass: a value spliced in for one token is never
        rescanned for another token.
        """
        weird = _entity([(0, 12)], "<<PERSON:2>>")
        bob = _entity([(20, 23)], "Bob")
        anonymizer = Anonymizer(LabelCounterPlaceholderFactory())
        tokens = anonymizer.create([weird, bob])
        assert anonymizer.deanonymize("<<PERSON:1>>", tokens) == "<<PERSON:2>>"
