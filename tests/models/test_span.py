"""Tests for the Span primitive."""

import dataclasses

import pytest

from piighost.exceptions import (
    NegativeSpanStartError,
    PIIGhostError,
    SpanError,
    SpanOrderingError,
)
from piighost.models import Span


class TestConstruction:
    def test_valid_span_sets_bounds(self) -> None:
        """A valid span stores its start and end."""
        s = Span(2, 5)
        assert s.start == 2
        assert s.end == 5

    def test_length_is_end_minus_start(self) -> None:
        """length is end minus start."""
        assert Span(2, 5).length == 3

    def test_len_matches_length(self) -> None:
        """len() returns the same value as length."""
        s = Span(0, 4)
        assert len(s) == s.length == 4

    def test_single_character_span(self) -> None:
        """A one-character span has length 1."""
        assert Span(3, 4).length == 1


class TestImmutability:
    def test_assignment_raises(self) -> None:
        """Assigning to a field raises because the dataclass is frozen."""
        s = Span(0, 5)
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(s, "start", 1)

    def test_uses_slots(self) -> None:
        """The class defines __slots__ for start and end."""
        assert "start" in Span.__slots__
        assert "end" in Span.__slots__

    def test_no_instance_dict(self) -> None:
        """A frozen slotted instance has no __dict__."""
        assert not hasattr(Span(0, 5), "__dict__")

    def test_hashable_and_dedupes_by_value(self) -> None:
        """Equal spans hash equal and deduplicate in a set."""
        assert hash(Span(0, 5)) == hash(Span(0, 5))
        assert len({Span(0, 5), Span(0, 5), Span(1, 2)}) == 2  # len(set(...)) == 2


class TestValidation:
    @pytest.mark.parametrize("start", [-1, -5, -100])
    def test_negative_start_raises(self, start: int) -> None:
        """A negative start raises NegativeSpanStartError."""
        with pytest.raises(NegativeSpanStartError):
            Span(start, 5)

    def test_empty_span_raises(self) -> None:
        """An empty range where end equals start raises SpanOrderingError."""
        with pytest.raises(SpanOrderingError):
            Span(3, 3)

    def test_reversed_span_raises(self) -> None:
        """A reversed range where end is below start raises SpanOrderingError."""
        with pytest.raises(SpanOrderingError):
            Span(5, 3)

    @pytest.mark.parametrize("bad", [(-1, 3), (3, 3), (5, 3)])
    def test_every_invalid_case_is_a_span_error(self, bad: tuple[int, int]) -> None:
        """Every invalid construction raises a SpanError."""
        with pytest.raises(SpanError):
            Span(*bad)

    @pytest.mark.parametrize("bad", [(-1, 3), (3, 3), (5, 3)])
    def test_every_invalid_case_is_a_piighost_error(self, bad: tuple[int, int]) -> None:
        """Every invalid construction raises a PIIGhostError."""
        with pytest.raises(PIIGhostError):
            Span(*bad)

    def test_error_message_reports_the_offending_start(self) -> None:
        """The error message includes the offending start value."""
        with pytest.raises(NegativeSpanStartError, match="-2"):
            Span(-2, 4)

    def test_error_message_reports_the_offending_bounds(self) -> None:
        """The error message includes the offending start and end."""
        with pytest.raises(SpanOrderingError, match="start=5, end=3"):
            Span(5, 3)


class TestOverlaps:
    def test_partial_overlap_both_directions(self) -> None:
        """Partially overlapping spans overlap, whichever the order."""
        assert Span(0, 5).overlaps(Span(3, 8))
        assert Span(3, 8).overlaps(Span(0, 5))

    def test_containment_overlaps(self) -> None:
        """A span containing another overlaps it, whichever the order."""
        assert Span(0, 10).overlaps(Span(3, 6))
        assert Span(3, 6).overlaps(Span(0, 10))

    def test_identical_spans_overlap(self) -> None:
        """Identical spans overlap."""
        assert Span(2, 7).overlaps(Span(2, 7))

    def test_disjoint_do_not_overlap(self) -> None:
        """Disjoint spans do not overlap."""
        assert not Span(0, 3).overlaps(Span(5, 9))

    def test_adjacent_spans_do_not_overlap(self) -> None:
        """Adjacent half-open spans touch but do not overlap."""
        # Half-open [0, 5) and [5, 10) touch but share no character.
        assert not Span(0, 5).overlaps(Span(5, 10))
        assert not Span(5, 10).overlaps(Span(0, 5))

    def test_overlaps_is_symmetric(self) -> None:
        """overlaps gives the same answer in both directions."""
        a, b = Span(0, 5), Span(4, 9)
        assert a.overlaps(b) == b.overlaps(a)


class TestContains:
    def test_contains_inner_span(self) -> None:
        """A span contains a strictly inner span."""
        assert Span(0, 10).contains(Span(2, 5))

    def test_contains_itself(self) -> None:
        """A span contains itself."""
        assert Span(2, 7).contains(Span(2, 7))

    def test_contains_span_sharing_a_boundary(self) -> None:
        """A span contains one that shares a boundary."""
        assert Span(0, 10).contains(Span(0, 4))
        assert Span(0, 10).contains(Span(6, 10))

    def test_does_not_contain_partial_overlap(self) -> None:
        """A partially overlapping span is not contained."""
        assert not Span(0, 5).contains(Span(3, 8))

    def test_does_not_contain_disjoint_span(self) -> None:
        """A disjoint span is not contained."""
        assert not Span(0, 3).contains(Span(5, 9))

    def test_containment_is_directional(self) -> None:
        """Containment holds one way and not the reverse."""
        outer, inner = Span(0, 10), Span(2, 5)
        assert outer.contains(inner)
        assert not inner.contains(outer)


class TestShift:
    def test_positive_shift(self) -> None:
        """A positive shift moves both bounds to the right."""
        assert Span(2, 5).shift(3) == Span(5, 8)

    def test_negative_shift(self) -> None:
        """A negative shift moves both bounds to the left."""
        assert Span(5, 8).shift(-3) == Span(2, 5)

    def test_zero_shift_returns_equal_span(self) -> None:
        """Shifting by zero returns an equal span."""
        s = Span(2, 5)
        assert s.shift(0) == s

    def test_shift_preserves_length(self) -> None:
        """A shift preserves the span length."""
        assert Span(2, 5).shift(10).length == 3

    def test_shift_below_zero_raises(self) -> None:
        """A shift pushing start below zero raises NegativeSpanStartError."""
        with pytest.raises(NegativeSpanStartError):
            Span(2, 5).shift(-3)

    def test_shift_returns_a_new_instance(self) -> None:
        """shift returns a new span and leaves the original unchanged."""
        original = Span(2, 5)
        shifted = original.shift(1)
        assert shifted is not original
        assert original == Span(2, 5)


class TestExtract:
    def test_extract_middle(self) -> None:
        """extract returns the substring in the middle of the text."""
        assert Span(7, 12).extract("Hello, world!") == "world"

    def test_extract_start(self) -> None:
        """extract returns the substring at the start of the text."""
        assert Span(0, 5).extract("Hello, world!") == "Hello"

    def test_extract_end(self) -> None:
        """extract returns the substring at the end of the text."""
        assert Span(3, 5).extract("Hello") == "lo"

    def test_extract_single_character(self) -> None:
        """extract returns a single character."""
        assert Span(0, 1).extract("abc") == "a"

    def test_extract_full_text(self) -> None:
        """extract over the whole range returns the full text."""
        text = "abc"
        assert Span(0, 3).extract(text) == text


class TestOrderingAndEquality:
    def test_equality_by_value(self) -> None:
        """Spans compare equal by value."""
        assert Span(2, 5) == Span(2, 5)
        assert Span(2, 5) != Span(2, 6)
        assert Span(2, 5) != Span(1, 5)

    def test_sorts_by_start_then_end(self) -> None:
        """Spans sort by start, then by end."""
        spans = [Span(5, 9), Span(0, 3), Span(0, 8), Span(2, 4)]
        assert sorted(spans) == [Span(0, 3), Span(0, 8), Span(2, 4), Span(5, 9)]

    def test_repr_reports_both_bounds(self) -> None:
        """repr includes both bounds."""
        r = repr(Span(2, 5))
        assert "2" in r
        assert "5" in r
