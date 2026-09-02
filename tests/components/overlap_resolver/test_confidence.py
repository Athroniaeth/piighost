"""Tests for the ConfidenceOverlapResolver."""

from piighost.components.overlap_resolver import (
    AnyOverlapResolver,
    BaseOverlapResolver,
    ConfidenceOverlapResolver,
)
from piighost.models import Detection, Span


def _detection(start: int, end: int, label: str, confidence: float) -> Detection:
    """Build a detection at [start, end) with the given label and confidence."""
    span = Span(start, end)
    text = "x" * (end - start)
    return Detection(
        span=span,
        label=label,
        confidence=confidence,
        text=text,
    )


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """ConfidenceOverlapResolver is an AnyOverlapResolver."""
        assert isinstance(ConfidenceOverlapResolver(), AnyOverlapResolver)


class TestResolve:
    def test_empty_returns_empty(self) -> None:
        """No detections resolve to none."""
        assert ConfidenceOverlapResolver().resolve([]) == []

    def test_non_overlapping_are_all_kept(self) -> None:
        """Detections that do not overlap are all kept."""
        a = _detection(0, 4, "PERSON", 0.9)
        b = _detection(10, 14, "EMAIL", 0.8)
        assert ConfidenceOverlapResolver().resolve([b, a]) == [a, b]

    def test_overlap_keeps_the_most_confident(self) -> None:
        """Between two overlapping detections, the most confident is kept."""
        weak = _detection(0, 8, "PERSON", 0.6)
        strong = _detection(4, 12, "COMPANY", 0.9)
        assert ConfidenceOverlapResolver().resolve([weak, strong]) == [strong]

    def test_same_span_conflict_is_resolved_by_confidence(self) -> None:
        """A same-span label conflict keeps the most confident detection."""
        person = _detection(0, 8, "PERSON", 0.7)
        company = _detection(0, 8, "COMPANY", 0.9)
        assert ConfidenceOverlapResolver().resolve([person, company]) == [company]

    def test_true_tie_keeps_the_first_detector(self) -> None:
        """On a same-span, same-confidence tie, the first detector in order wins.

        The list is passed in detector order (a CompositeDetector concatenates
        its children in order), so the earliest detector's detection is kept.
        """
        first = _detection(0, 5, "LOCATION", 1.0)
        second = _detection(0, 5, "PERSON", 1.0)
        assert ConfidenceOverlapResolver().resolve([first, second]) == [first]

    def test_result_is_in_position_order(self) -> None:
        """The kept detections are returned sorted by position."""
        first = _detection(0, 4, "PERSON", 0.5)
        second = _detection(10, 14, "EMAIL", 0.9)
        resolved = ConfidenceOverlapResolver().resolve([second, first])
        assert [detection.span for detection in resolved] == [Span(0, 4), Span(10, 14)]


class TestTemplate:
    def test_reduce_hook_drives_the_choice(self) -> None:
        """A subclass's _reduce decides which overlapping detections win."""

        class LongestOverlapResolver(BaseOverlapResolver):
            def _reduce(self, conflicting: list[Detection]) -> list[Detection]:
                """Keep the single longest detection in the group."""
                longest = conflicting[0]

                for detection in conflicting:
                    if detection.span.length > longest.span.length:
                        longest = detection
                return [longest]

        short = _detection(0, 4, "PERSON", 0.9)
        wide = _detection(0, 8, "COMPANY", 0.1)
        assert ConfidenceOverlapResolver().resolve([short, wide]) == [short]
        assert LongestOverlapResolver().resolve([short, wide]) == [wide]
