"""Tests for word-boundary matching."""

import re
import sys
import unicodedata

import pytest

from piighost.exceptions import EmptyFragmentError
from piighost.models import Span
from piighost.text import boundary_wrap, clear_boundary_cache, find_all_word_boundary
from piighost.text.boundaries import WORD_JOIN_CHARS, _word_boundary_pattern

HYPHENS = [
    pytest.param("-", id="hyphen-minus"),
    pytest.param("\u2011", id="non-breaking-hyphen"),
    pytest.param("\u00ad", id="soft-hyphen"),
    pytest.param("\u05be", id="maqaf"),
]
"""The ASCII hyphen, and three others that Word or a script writes in its place."""

DASHES = [
    pytest.param("\u2013", id="en-dash"),
    pytest.param("\u2014", id="em-dash"),
]
"""Dashes, which separate two words rather than join them."""


class TestFindAllWordBoundary:
    def test_finds_a_whole_word(self) -> None:
        """A fragment standing as a whole word is found."""
        assert find_all_word_boundary("Jean is here", "Jean") == [Span(0, 4)]

    def test_does_not_match_inside_a_longer_word(self) -> None:
        """A fragment glued to more letters is not a whole-word match."""
        assert find_all_word_boundary("Jeanne is here", "Jean") == []

    @pytest.mark.parametrize("hyphen", HYPHENS)
    def test_a_hyphen_joins_words(self, hyphen: str) -> None:
        """Jean is not matched inside Jean-Paul, whichever hyphen joins them."""
        assert find_all_word_boundary(f"Jean{hyphen}Paul is here", "Jean") == []

    @pytest.mark.parametrize("dash", DASHES)
    def test_a_dash_bounds_a_word(self, dash: str) -> None:
        """Paris is found when a dash, not a hyphen, stands between it and Lyon."""
        assert find_all_word_boundary(f"Paris{dash}Lyon", "Paris") == [Span(0, 5)]

    def test_hyphens_are_the_dash_punctuation_named_hyphen(self) -> None:
        """WORD_JOIN_CHARS is every Pd character named a hyphen, and the soft one.

        The list follows the newest Unicode a supported Python ships, so an
        older interpreter does not know some of its characters yet: only the
        ones this interpreter has assigned are compared.
        """
        every_char = (chr(code) for code in range(sys.maxunicode + 1))
        named = {
            char
            for char in every_char
            if unicodedata.category(char) == "Pd"
            and any(word in unicodedata.name(char) for word in ("HYPHEN", "MAQAF"))
        }
        known = {char for char in WORD_JOIN_CHARS if unicodedata.category(char) != "Cn"}
        assert known == named | {"\u00ad"}

    @pytest.mark.parametrize(
        ("text", "fragment", "span"),
        [
            ("bonjour d'Anne", "Anne", Span(10, 14)),
            ("le notaire d'Ille-et-Vilaine", "Ille-et-Vilaine", Span(13, 28)),
            ("la pratica dell'Anna", "Anna", Span(16, 20)),
            ("chez d\u2019Anne", "Anne", Span(7, 11)),
            ("Jean's car", "Jean", Span(0, 4)),
            ("the Jones' house", "Jones", Span(4, 9)),
            ("he said 'Jean' twice", "Jean", Span(9, 13)),
        ],
    )
    def test_an_apostrophe_bounds_a_word(
        self, text: str, fragment: str, span: Span
    ) -> None:
        """An apostrophe ends or starts a word, whatever the language."""
        assert find_all_word_boundary(text, fragment) == [span]

    def test_a_fragment_inside_an_apostrophe_compound_is_found(self) -> None:
        """Brien is found inside O'Brien, the accepted cost of a boundary apostrophe."""
        assert find_all_word_boundary("Mr O'Brien is here", "Brien") == [Span(5, 10)]

    def test_a_fragment_with_an_apostrophe_is_matched_whole(self) -> None:
        """A value that holds an apostrophe is found as itself."""
        assert find_all_word_boundary("Mr O'Brien is here", "O'Brien") == [Span(3, 10)]

    def test_finds_every_occurrence(self) -> None:
        """Every whole-word occurrence is returned, in order."""
        assert find_all_word_boundary("Jean and Jean", "Jean") == [
            Span(0, 4),
            Span(9, 13),
        ]

    def test_is_case_insensitive_by_default(self) -> None:
        """By default the match ignores case."""
        assert find_all_word_boundary("Hi JEAN", "jean") == [Span(3, 7)]

    def test_case_sensitive_when_asked(self) -> None:
        """With no ignore-case flag, the match is exact case."""
        assert find_all_word_boundary("Hi JEAN", "jean", flags=re.NOFLAG) == []

    def test_fragment_is_matched_literally(self) -> None:
        """Regex metacharacters in the fragment are matched literally."""
        assert find_all_word_boundary("code a.b here", "a.b") == [Span(5, 8)]

    def test_empty_fragment_is_refused(self) -> None:
        """An empty fragment raises rather than yield a zero-width span."""
        with pytest.raises(EmptyFragmentError):
            find_all_word_boundary("Hello, world!", "")


class TestBoundaryWrap:
    def test_empty_fragment_is_refused(self) -> None:
        """boundary_wrap refuses an empty fragment, which matches everywhere."""
        with pytest.raises(EmptyFragmentError):
            boundary_wrap("")


class TestClearBoundaryCache:
    def test_drops_the_compiled_patterns(self) -> None:
        """Clearing the cache leaves no compiled pattern, so no fragment is held."""
        find_all_word_boundary("Jean is here", "Jean")
        clear_boundary_cache()
        assert _word_boundary_pattern.cache_info().currsize == 0


SPACES = [
    pytest.param("\u00a0", id="no-break-space"),
    pytest.param("\u3000", id="ideographic-space"),
]
"""Two Unicode spaces standing for all of them.

test_normalization checks every separator one by one. Here two are enough to
show the component reads spaces through normalize_spaces.
"""

SPACING_VARIANTS = [
    pytest.param("Paul  Martin", id="two-spaces"),
    pytest.param("Paul\nMartin", id="line-break"),
    pytest.param("Paul\u2028Martin", id="line-separator"),
    pytest.param("Paul \u00a0Martin", id="mixed-run"),
    pytest.param("Paul\tMartin", id="tab"),
]
"""Ways a text separates the two words of a value."""


class TestUnicodeSpaces:
    @pytest.mark.parametrize("space", SPACES)
    def test_a_space_in_the_fragment_matches_any_space(self, space: str) -> None:
        """A value searched with an ordinary space is found with any Unicode one."""
        text = f"signé Paul{space}Martin."
        assert find_all_word_boundary(text, "Paul Martin") == [Span(6, 17)]

    @pytest.mark.parametrize("space", SPACES)
    def test_a_fragment_with_a_unicode_space_finds_an_ordinary_one(
        self, space: str
    ) -> None:
        """A value detected with a Unicode space is found written with U+0020."""
        text = "signé Paul Martin."
        assert find_all_word_boundary(text, f"Paul{space}Martin") == [Span(6, 17)]

    @pytest.mark.parametrize("text", SPACING_VARIANTS)
    def test_any_run_of_whitespace_separates_the_words(self, text: str) -> None:
        """The words of a value are found whatever whitespace runs between them."""
        (span,) = find_all_word_boundary(text, "Paul Martin")
        assert (span.start, span.end) == (0, len(text))

    def test_the_last_word_still_has_to_end(self) -> None:
        """A flexible space does not relax the whole-word rule at the edges."""
        assert find_all_word_boundary("Paul\u00a0Martine", "Paul Martin") == []

    @pytest.mark.parametrize("fragment", [" ", "\u00a0", "\u3000 \n"])
    def test_a_whitespace_only_fragment_is_refused(self, fragment: str) -> None:
        """A fragment with no word matches everywhere, so it is refused."""
        with pytest.raises(EmptyFragmentError):
            find_all_word_boundary("some text", fragment)
