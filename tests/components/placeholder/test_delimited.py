"""Tests for the delimited placeholder base: custom delimiters and recognition."""

import pytest

from piighost.components.placeholder import (
    LabelCounterPlaceholderFactory,
    LabelHashPlaceholderFactory,
    LabelPlaceholderFactory,
    RedactPlaceholderFactory,
)
from piighost.components.placeholder.base import AnyPlaceholderFactory
from piighost.models import Detection, Entity, Span


def _entity(text: str, label: str = "PERSON") -> Entity:
    """Build a single-detection entity for the given text and label."""
    detection = Detection(
        span=Span(0, len(text)), text=text, label=label, confidence=0.9
    )
    return Entity((detection,))


class TestCustomDelimiters:
    @pytest.mark.parametrize(
        ("factory", "expected"),
        [
            (LabelPlaceholderFactory("[[", "]]"), "[[PERSON]]"),
            (LabelCounterPlaceholderFactory("[[", "]]"), "[[PERSON:1]]"),
            (RedactPlaceholderFactory("[[", "]]"), "[[REDACT]]"),
        ],
    )
    def test_delimiters_wrap_the_token(
        self, factory: AnyPlaceholderFactory, expected: str
    ) -> None:
        """Custom delimiters replace the default << >> around the inner form."""
        entity = _entity("Emma")
        assert factory.create([entity])[entity] == expected

    def test_default_delimiters_are_angle_brackets(self) -> None:
        """Left untouched, a factory still wraps its tokens in << >>."""
        entity = _entity("Emma")
        assert (
            LabelCounterPlaceholderFactory().create([entity])[entity] == "<<PERSON:1>>"
        )

    def test_hash_factory_keeps_its_own_argument(self) -> None:
        """The hash factory composes hash_length with the delimiters."""
        entity = _entity("Emma")
        factory = LabelHashPlaceholderFactory(hash_length=4, prefix="[[", suffix="]]")
        token = factory.create([entity])[entity]
        assert token.startswith("[[PERSON:") and token.endswith("]]")
        assert len(token) == len("[[PERSON:]]") + 4


class TestRecognition:
    def test_find_tokens_returns_each_occurrence_in_order(self) -> None:
        """Every token in the text is found, whole, in reading order."""
        factory = LabelCounterPlaceholderFactory()
        text = "Contact <<PERSON:1>> or <<EMAIL:1>>, not <<PERSON:1>>."
        found = factory.find_tokens(text)
        assert found == ["<<PERSON:1>>", "<<EMAIL:1>>", "<<PERSON:1>>"]

    def test_find_tokens_follows_custom_delimiters(self) -> None:
        """A factory finds tokens shaped like the delimiters it emits."""
        factory = LabelCounterPlaceholderFactory("[[", "]]")
        assert factory.find_tokens("a [[PERSON:1]] b <<PERSON:1>>") == ["[[PERSON:1]]"]

    def test_pattern_captures_the_inner_form(self) -> None:
        """The capturing group exposes the inner form without the delimiters."""
        factory = LabelCounterPlaceholderFactory()
        match = factory.token_pattern.search("x <<PERSON:1>> y")
        assert match is not None
        assert match.group(1) == "PERSON:1"

    def test_no_token_yields_no_match(self) -> None:
        """Plain text carries no tokens."""
        assert LabelCounterPlaceholderFactory().find_tokens("nothing here") == []

    def test_arbitrary_delimited_content_is_not_a_token(self) -> None:
        """Stray << >> around non-token content is not matched (C++, markdown).

        The old .+? grammar treated any <<...>> as a token, so C++ shifts and
        markdown tripped the invented-token guard. The inner form is now bounded.
        """
        factory = LabelCounterPlaceholderFactory()
        assert factory.find_tokens("cout << x >> y") == []
        assert factory.find_tokens("a << b >> c") == []
        assert factory.find_tokens("shift <<= 2 and >>= 1") == []

    def test_real_token_forms_stay_recognized(self) -> None:
        """The counter, hash, label, and redact token shapes still match."""
        counter = LabelCounterPlaceholderFactory()
        assert counter.find_tokens("<<PERSON:1>>") == ["<<PERSON:1>>"]
        hasher = LabelHashPlaceholderFactory()
        assert hasher.find_tokens("<<PERSON:6b86b273>>") == ["<<PERSON:6b86b273>>"]
        label = LabelPlaceholderFactory()
        assert label.find_tokens("<<PERSON>>") == ["<<PERSON>>"]
        redact = RedactPlaceholderFactory()
        assert redact.find_tokens("<<REDACT>>") == ["<<REDACT>>"]

    def test_multi_word_label_with_spaces_is_recognized(self) -> None:
        """A label carrying spaces, as an LLM detector may emit, still matches."""
        counter = LabelCounterPlaceholderFactory()
        assert counter.find_tokens("<<date of birth:1>>") == ["<<date of birth:1>>"]
