"""Tests for space normalization and value identity."""

import sys
import unicodedata

import pytest

from piighost.text import (
    LINE_SEPARATORS,
    SPACE_SEPARATORS,
    normalize_spaces,
    value_key,
)

SPACES = [pytest.param(char, id=f"U+{ord(char):04X}") for char in SPACE_SEPARATORS]
"""Every Unicode space separator but U+0020, one test case each."""

LINES = [pytest.param(char, id=f"U+{ord(char):04X}") for char in LINE_SEPARATORS]
"""Every Unicode line separator but the newline, one test case each."""

UNTOUCHED = [
    pytest.param("\t", id="tab"),
    pytest.param("\u200b", id="zero-width-space"),
    pytest.param("\u2060", id="word-joiner"),
    pytest.param("\ufeff", id="byte-order-mark"),
    pytest.param("\u2011", id="non-breaking-hyphen"),
    pytest.param("é", id="letter"),
]
"""Characters that are not space separators, so normalization keeps them."""

SAME_VALUE = [
    pytest.param("Paul Martin", "Paul\u00a0Martin", id="no-break-space"),
    pytest.param("Paul Martin", "Paul\u202fMartin", id="narrow-no-break-space"),
    pytest.param("Paul Martin", "Paul\u3000Martin", id="ideographic-space"),
    pytest.param("Paul Martin", "Paul  Martin", id="two-spaces"),
    pytest.param("Paul Martin", "Paul\nMartin", id="line-break"),
    pytest.param("Paul Martin", "Paul\u2028Martin", id="line-separator"),
    pytest.param("Paul Martin", " Paul Martin ", id="outer-spaces"),
    pytest.param("Paul Martin", "PAUL martin", id="case"),
    pytest.param("Straße", "STRASSE", id="full-case-folding"),
]
"""Pairs of spellings that name one value."""

OTHER_VALUE = [
    pytest.param("Paul Martin", "PaulMartin", id="no-space"),
    pytest.param("Paul Martin", "Paul\u200bMartin", id="zero-width-space"),
    pytest.param("Paul Martin", "Paul-Martin", id="hyphen"),
    pytest.param("Paul Martin", "Paul Martine", id="another-word"),
]
"""Pairs of spellings that name two values."""


def _category_members(*categories: str) -> set[str]:
    """Return every code point whose Unicode category is one of the given ones."""
    return {
        chr(code)
        for code in range(sys.maxunicode + 1)
        if unicodedata.category(chr(code)) in categories
    }


class TestSeparators:
    def test_space_separators_are_the_whole_zs_category_but_ascii(self) -> None:
        """SPACE_SEPARATORS is exactly Unicode's Zs category without U+0020."""
        assert set(SPACE_SEPARATORS) == _category_members("Zs") - {" "}

    def test_line_separators_are_zl_zp_and_next_line(self) -> None:
        """LINE_SEPARATORS is exactly the Zl and Zp categories plus U+0085."""
        assert set(LINE_SEPARATORS) == _category_members("Zl", "Zp") | {"\u0085"}

    def test_every_separator_is_whitespace_to_python(self) -> None:
        """str.split and the Unicode whitespace class treat every separator as a space."""
        assert all(char.isspace() for char in SPACE_SEPARATORS + LINE_SEPARATORS)


class TestNormalizeSpaces:
    @pytest.mark.parametrize("space", SPACES)
    def test_a_space_separator_becomes_an_ascii_space(self, space: str) -> None:
        """Each space separator is read as U+0020."""
        assert normalize_spaces(f"06{space}12") == "06 12"

    @pytest.mark.parametrize("line", LINES)
    def test_a_line_separator_becomes_a_newline(self, line: str) -> None:
        """Each line separator is read as a newline."""
        assert normalize_spaces(f"one{line}two") == "one\ntwo"

    @pytest.mark.parametrize("char", UNTOUCHED)
    def test_other_characters_are_kept(self, char: str) -> None:
        """A character that is not a space separator is left as it is."""
        assert normalize_spaces(f"a{char}b") == f"a{char}b"

    def test_the_length_is_kept_so_offsets_hold(self) -> None:
        """The result has the text's length, character for character."""
        text = "\u3000Tél.\u00a006\u202f12\u2028" + SPACE_SEPARATORS + LINE_SEPARATORS
        normalized = normalize_spaces(text)
        assert len(normalized) == len(text)
        assert [char for char in normalized if char not in " \n"] == [
            char for char in text if char not in SPACE_SEPARATORS + LINE_SEPARATORS
        ]


class TestValueKey:
    @pytest.mark.parametrize(("first", "second"), SAME_VALUE)
    def test_two_spellings_of_one_value_share_a_key(
        self, first: str, second: str
    ) -> None:
        """Spaces, their number and case do not change a value's key."""
        assert value_key(first) == value_key(second)

    @pytest.mark.parametrize(("first", "second"), OTHER_VALUE)
    def test_two_values_have_two_keys(self, first: str, second: str) -> None:
        """Words that differ, or are not separated by whitespace, stay apart."""
        assert value_key(first) != value_key(second)
