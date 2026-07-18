"""Tests for the Detection model."""

import dataclasses

import pytest

from piighost.exceptions import ConfidenceError
from piighost.models import Detection, Span


def _detection(confidence: float = 0.9) -> Detection:
    """Build a valid detection with the given confidence."""
    span = Span(0, 4)
    return Detection(
        span=span,
        label="PERSON",
        confidence=confidence,
        text="Emma",
    )


def _at(start: int, end: int, label: str = "PERSON") -> Detection:
    """Build a detection covering [start, end) with the given label."""
    span = Span(start, end)
    return Detection(
        span=span,
        text="x" * (end - start),
        label=label,
        confidence=0.9,
    )


class TestConstruction:
    def test_stores_all_fields(self) -> None:
        """A valid detection stores its span, label, confidence, and text."""
        span = Span(0, 4)
        d = Detection(
            span=span,
            label="PERSON",
            confidence=0.9,
            text="Emma",
        )
        assert d.span == span
        assert d.label == "PERSON"
        assert d.confidence == 0.9
        assert d.text == "Emma"

    def test_assignment_raises(self) -> None:
        """Assigning to a field raises because the dataclass is frozen."""
        d = _detection()
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(d, "label", "EMAIL")

    def test_no_instance_dict(self) -> None:
        """A frozen slotted instance has no __dict__."""
        assert not hasattr(_detection(), "__dict__")

    def test_equal_detections_are_equal(self) -> None:
        """Detections compare equal by value."""
        assert _detection() == _detection()

    def test_hashable_and_dedupes_by_value(self) -> None:
        """Equal detections hash equal and deduplicate in a set."""
        assert len({_detection(), _detection()}) == 1


class TestOrdering:
    def test_sorts_by_span_first(self) -> None:
        """Detections sort by span position first."""
        later_span = Span(5, 9)
        later = Detection(
            span=later_span,
            label="EMAIL",
            confidence=0.5,
            text="a@b.c",
        )
        earlier_span = Span(0, 4)
        earlier = Detection(
            span=earlier_span,
            label="PERSON",
            confidence=0.9,
            text="Emma",
        )
        assert sorted([later, earlier]) == [earlier, later]


class TestConfidenceValidation:
    @pytest.mark.parametrize("confidence", [0.0, 0.5, 1.0])
    def test_confidence_in_range_is_accepted(self, confidence: float) -> None:
        """A confidence within 0 to 1, bounds included, is accepted."""
        assert _detection(confidence).confidence == confidence

    @pytest.mark.parametrize("confidence", [-0.1, -1.0, 1.1, 2.0])
    def test_confidence_out_of_range_raises(self, confidence: float) -> None:
        """A confidence outside 0 to 1 raises ConfidenceError."""
        with pytest.raises(ConfidenceError):
            _detection(confidence)

    def test_error_message_reports_the_bad_value(self) -> None:
        """The error message includes the offending confidence."""
        with pytest.raises(ConfidenceError, match="1.5"):
            _detection(1.5)


class TestOverlaps:
    def test_overlapping_detections_overlap(self) -> None:
        """Detections whose spans overlap report overlap, in both directions."""
        assert _at(0, 5).overlaps(_at(3, 8))
        assert _at(3, 8).overlaps(_at(0, 5))

    def test_disjoint_detections_do_not_overlap(self) -> None:
        """Detections whose spans are disjoint do not overlap."""
        assert not _at(0, 3).overlaps(_at(5, 9))
