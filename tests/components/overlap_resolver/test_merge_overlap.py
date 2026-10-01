"""Tests for the MergeOverlapResolver."""

from itertools import pairwise

import pytest

from piighost.components.overlap_resolver import (
    AnyOverlapResolver,
    MergeOverlapResolver,
)
from piighost.models import Detection, Span

TEXT = "Monsieur Loni M. Wirth signe au 12 rue des Lilas, 75008 Paris."
"""The text every detection of this module is cut from, so spans stay honest."""


def _detection(value: str, label: str, confidence: float) -> Detection:
    """Build a detection covering the first occurrence of value in TEXT."""
    start = TEXT.index(value)
    span = Span(start, start + len(value))
    return Detection(
        span=span,
        text=value,
        label=label,
        confidence=confidence,
    )


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """MergeOverlapResolver is an AnyOverlapResolver."""
        assert isinstance(MergeOverlapResolver(), AnyOverlapResolver)


class TestResolve:
    def test_empty_returns_empty(self) -> None:
        """No detections resolve to none."""
        assert MergeOverlapResolver().resolve([]) == []

    def test_disjoint_detections_are_kept_as_they_are(self) -> None:
        """Detections that do not overlap pass through untouched."""
        name = _detection("Loni M. Wirth", "PERSON", 0.7)
        street = _detection("12 rue des Lilas", "ADDRESS", 1.0)
        assert MergeOverlapResolver().resolve([street, name]) == [name, street]

    def test_a_shorter_sure_span_does_not_cut_a_longer_one(self) -> None:
        """A rule's short sure span is widened to the model's, so nothing is left in clear."""
        rule = _detection("Wirth", "FR_CIVIL_NAME", 1.0)
        model = _detection("Loni M. Wirth", "PERSON", 0.7)
        (merged,) = MergeOverlapResolver().resolve([rule, model])
        assert merged.text == "Loni M. Wirth"
        assert merged.span == model.span

    def test_the_union_takes_the_surest_label_and_confidence(self) -> None:
        """The merged detection carries the most confident member's label."""
        street = _detection("12 rue des Lilas", "FR_STREET", 1.0)
        address = _detection("rue des Lilas, 75008 Paris", "ADDRESS", 0.6)
        (merged,) = MergeOverlapResolver().resolve([address, street])
        assert merged.text == "12 rue des Lilas, 75008 Paris"
        assert (merged.label, merged.confidence) == ("FR_STREET", 1.0)

    def test_a_chain_of_overlaps_becomes_one_span(self) -> None:
        """A overlaps B and B overlaps C, so the three merge even if A misses C."""
        first = _detection("Monsieur Loni", "PERSON", 0.5)
        middle = _detection("Loni M.", "PERSON", 0.6)
        last = _detection("M. Wirth", "FR_CIVIL_NAME", 1.0)
        (merged,) = MergeOverlapResolver().resolve([first, middle, last])
        assert merged.text == "Monsieur Loni M. Wirth"

    def test_an_earlier_span_wins_at_equal_confidence(self) -> None:
        """At equal confidence the member that starts first gives its label."""
        late = _detection("M. Wirth", "LATE", 0.9)
        early = _detection("Loni M. Wirth", "EARLY", 0.9)
        (merged,) = MergeOverlapResolver().resolve([late, early])
        assert merged.label == "EARLY"

    @pytest.mark.parametrize("labels", [("FIRST", "SECOND"), ("SECOND", "FIRST")])
    def test_a_true_tie_keeps_the_first_detector_label(
        self, labels: tuple[str, str]
    ) -> None:
        """On one span at one confidence, the detection listed first wins."""
        tied = [_detection("Loni M. Wirth", label, 0.9) for label in labels]
        wider = _detection("Monsieur Loni", "WIDER", 0.5)
        (merged,) = MergeOverlapResolver().resolve([*tied, wider])
        assert merged.label == labels[0]

    def test_the_result_never_overlaps(self) -> None:
        """Whatever the input, no two kept detections overlap."""
        detections = [
            _detection("Monsieur Loni", "PERSON", 0.5),
            _detection("Wirth", "FR_CIVIL_NAME", 1.0),
            _detection("Loni M. Wirth", "PERSON", 0.7),
            _detection("12 rue des Lilas", "FR_STREET", 1.0),
            _detection("75008 Paris", "ADDRESS", 0.4),
        ]
        kept = MergeOverlapResolver().resolve(detections)
        for before, after in pairwise(kept):
            assert before.span.end <= after.span.start
