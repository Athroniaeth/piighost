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

    def test_apostrophe_counts_as_word_internal(self) -> None:
        """An apostrophe joins words, so Anne is not matched inside d'Anne."""
        assert find_all_word_boundary("bonjour d'Anne", "Anne") == []

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
