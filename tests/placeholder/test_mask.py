"""Tests for the MaskPlaceholderFactory."""

from piighost.models import Detection, Entity, Span
from piighost.placeholder import AnyPlaceholderFactory, MaskPlaceholderFactory
from piighost.placeholder.tags import PreservesShape


def _entity(start: int, end: int, text: str, label: str = "PERSON") -> Entity:
    """Build a single-detection entity for the given text and label."""
    detection = Detection(span=Span(start, end), text=text, label=label, confidence=0.9)
    return Entity((detection,))


def _mask(text: str, visible: int = 1, mask_char: str = "*") -> str:
    """Mask a single entity's text and return its token."""
    entity = _entity(0, len(text), text)
    factory = MaskPlaceholderFactory(visible=visible, mask_char=mask_char)
    return factory.create([entity])[entity]


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """MaskPlaceholderFactory is an AnyPlaceholderFactory."""
        assert isinstance(MaskPlaceholderFactory(), AnyPlaceholderFactory)


class TestCreate:
    def test_keeps_the_leading_character_and_masks_the_rest(self) -> None:
        """A value keeps its first character and stars out the rest."""
        assert _mask("Jonathan") == "J*******"

    def test_preserves_length(self) -> None:
        """The masked token is as long as the original value."""
        assert len(_mask("Jonathan")) == len("Jonathan")

    def test_visible_count_is_configurable(self) -> None:
        """More leading characters can be revealed."""
        assert _mask("Jonathan", visible=3) == "Jon*****"

    def test_mask_character_is_configurable(self) -> None:
        """The masking character can be changed."""
        assert _mask("Jonathan", mask_char="#") == "J#######"


class TestShortValues:
    def test_single_character_is_fully_masked(self) -> None:
        """A one-character value is masked, never revealed as itself."""
        assert _mask("J") == "*"

    def test_two_characters_reveal_at_most_one(self) -> None:
        """A two-character value keeps one character and masks the other."""
        assert _mask("Jo") == "J*"

    def test_reveal_never_exposes_the_whole_value(self) -> None:
        """A visible count above the length still masks the last character."""
        assert _mask("Jo", visible=5) == "J*"

    def test_always_masks_at_least_one_character(self) -> None:
        """However long the value, at least one character stays masked."""
        token = _mask("Jonathan", visible=100)
        assert token.endswith("*")
        assert token[:-1] == "Jonatha"


class TestSemantics:
    def test_same_shape_values_collide(self) -> None:
        """Two values with the same prefix and length share one token."""
        jean = _entity(0, 4, "Jean")
        jack = _entity(9, 13, "Jack")
        tokens = MaskPlaceholderFactory().create([jean, jack])
        assert tokens[jean] == tokens[jack] == "J***"

    def test_tokens_carry_the_preservation_tag(self) -> None:
        """A token is an instance of the factory's tag, and still a plain str."""
        entity = _entity(0, 4, "Emma")
        token = MaskPlaceholderFactory().create([entity])[entity]
        assert isinstance(token, PreservesShape)
        assert isinstance(token, str)

    def test_no_entities_yields_no_tokens(self) -> None:
        """Creating tokens for nothing returns an empty mapping."""
        assert MaskPlaceholderFactory().create([]) == {}
