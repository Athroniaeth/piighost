"""Tests for word-boundary matching."""

import re

import pytest

from piighost.exceptions import EmptyFragmentError
from piighost.models import Span
from piighost.text import boundary_wrap, clear_boundary_cache, find_all_word_boundary
from piighost.text.boundaries import _word_boundary_pattern


class TestFindAllWordBoundary:
    def test_finds_a_whole_word(self) -> None:
        """A fragment standing as a whole word is found."""
        assert find_all_word_boundary("Jean is here", "Jean") == [Span(0, 4)]

    def test_does_not_match_inside_a_longer_word(self) -> None:
        """A fragment glued to more letters is not a whole-word match."""
        assert find_all_word_boundary("Jeanne is here", "Jean") == []

    def test_hyphen_counts_as_word_internal(self) -> None:
        """A hyphen joins words, so Jean is not matched inside Jean-Paul."""
        assert find_all_word_boundary("Jean-Paul is here", "Jean") == []

    def test_apostrophe_inside_a_name_counts_as_word_internal(self) -> None:
        """An apostrophe inside a name joins it, so Brien is not found in O'Brien."""
        assert find_all_word_boundary("Mr O'Brien is here", "Brien") == []
        assert find_all_word_boundary("Mr O\u2019Brien is here", "Brien") == []

    @pytest.mark.parametrize(
        ("text", "fragment", "span"),
        [
            ("bonjour d'Anne", "Anne", Span(10, 14)),
            ("le notaire d'Ille-et-Vilaine", "Ille-et-Vilaine", Span(13, 28)),
            ("au nom de l'ACQUEREUR", "ACQUEREUR", Span(12, 21)),
            ("L'Oréal signe", "Oréal", Span(2, 7)),
            ("qu'Yvonne vienne", "Yvonne", Span(3, 9)),
            ("jusqu'Arras", "Arras", Span(6, 11)),
            ("lorsqu'Yvonne signe", "Yvonne", Span(7, 13)),
            ("chez d\u2019Anne", "Anne", Span(7, 11)),
        ],
    )
    def test_a_french_elision_is_a_boundary(
        self, text: str, fragment: str, span: Span
    ) -> None:
        """The apostrophe after an elided article or preposition ends that word."""
        assert find_all_word_boundary(text, fragment) == [span]

    def test_an_elision_needs_the_clitic_to_stand_alone(self) -> None:
        """A letter before an apostrophe elides only when it is a word of its own."""
        assert find_all_word_boundary("aujourd'hui", "hui") == []
        assert find_all_word_boundary("prud'homme", "homme") == []

    def test_an_elision_is_found_in_either_case(self) -> None:
        """The clitic is recognised whatever the case flags of the search."""
        assert find_all_word_boundary("D'Anne", "Anne", flags=re.NOFLAG) == [Span(2, 6)]
        assert find_all_word_boundary("QU'Anne", "Anne", flags=re.NOFLAG) == [
            Span(3, 7)
        ]

    @pytest.mark.parametrize(
        ("text", "span"),
        [
            ("Jean's car", Span(0, 4)),
            ("Jean\u2019s car", Span(0, 4)),
            ("the Jones' house", Span(4, 9)),
        ],
    )
    def test_an_english_possessive_is_a_boundary(self, text: str, span: Span) -> None:
        """A possessive ends the name it follows, like any punctuation."""
        fragment = text[span.start : span.end]
        assert find_all_word_boundary(text, fragment) == [span]

    def test_a_single_quote_around_a_name_is_a_boundary(self) -> None:
        """An apostrophe used as a quotation mark bounds the name it wraps."""
        assert find_all_word_boundary("he said 'Jean' twice", "Jean") == [Span(9, 13)]

    def test_a_possessive_needs_to_end_the_word(self) -> None:
        """An apostrophe then more letters is still inside the word."""
        assert find_all_word_boundary("O'Shea", "O") == []
        assert find_all_word_boundary("Jean'sen", "Jean") == []

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


class TestSameAsTheWrappedPattern:
    def test_the_search_agrees_with_boundary_wrap(self) -> None:
        """The literal-first search finds exactly what the wrapped pattern finds.

        find_all_word_boundary looks for the fragment as a literal and checks
        its two edges, instead of running the wrapped pattern, whose leading
        lookbehinds keep the regex engine from skipping ahead. The two must
        agree everywhere, overlapping candidates and rejected ones included.
        """
        import random

        rng = random.Random(20260927)
        pieces = ["a", "ab", " ", "-", "'", "’", "d'", "l'", "qu'", "s", "É", "."]
        fragments = ["ab", "a b", "ab ab", "s", "É", "a-b", "d'ab"]
        for _ in range(3000):
            text = "".join(rng.choice(pieces) for _ in range(rng.randint(1, 14)))
            for fragment in fragments:
                for flags in (re.IGNORECASE, re.NOFLAG):
                    expected = [
                        Span(m.start(), m.end())
                        for m in re.finditer(boundary_wrap(fragment), text, flags)
                    ]
                    assert find_all_word_boundary(text, fragment, flags) == expected, (
                        text,
                        fragment,
                        flags,
                    )
