"""Tests for the WordBoundaryExpander."""

from itertools import pairwise

from piighost.components.expander import AnyDetectionExpander, WordBoundaryExpander
from piighost.models import Detection, Span


def _detection(start: int, end: int, text: str, label: str = "PERSON") -> Detection:
    """Build a detection covering [start, end) for the given text and label."""
    span = Span(start, end)
    return Detection(
        span=span,
        text=text,
        label=label,
        confidence=0.9,
    )


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """WordBoundaryExpander is an AnyDetectionExpander."""
        assert isinstance(WordBoundaryExpander(), AnyDetectionExpander)


class TestExpand:
    def test_keeps_the_original_detections(self) -> None:
        """The original detections are returned."""
        detection = _detection(0, 4, "Emma")
        assert detection in WordBoundaryExpander().expand("Emma and Emma", [detection])

    def test_finds_a_missed_occurrence(self) -> None:
        """A repeat of a detected value that was missed is added."""
        detection = _detection(0, 4, "Emma")
        expanded = WordBoundaryExpander().expand("Emma and Emma", [detection])
        spans = sorted(found.span for found in expanded)
        assert spans == [Span(0, 4), Span(9, 13)]

    def test_finds_an_occurrence_glued_to_an_apostrophe(self) -> None:
        """A repeat right after an apostrophe is found, the apostrophe bounding the word."""
        text = "Ille-et-Vilaine, office notarial d'Ille-et-Vilaine"
        detection = _detection(0, 15, "Ille-et-Vilaine", label="LOCATION")
        expanded = WordBoundaryExpander().expand(text, [detection])
        spans = sorted(found.span for found in expanded)
        assert spans == [Span(0, 15), Span(35, 50)]

    def test_added_detection_inherits_label_and_confidence(self) -> None:
        """A found occurrence carries the source label and confidence."""
        detection = _detection(0, 4, "Emma", label="PERSON")
        expanded = WordBoundaryExpander().expand("Emma and Emma", [detection])
        found = next(item for item in expanded if item.span == Span(9, 13))
        assert found.label == "PERSON"
        assert found.confidence == detection.confidence
        assert found.text == "Emma"

    def test_no_missed_occurrence_returns_the_input(self) -> None:
        """When the value appears once, nothing is added."""
        detection = _detection(0, 4, "Emma")
        assert WordBoundaryExpander().expand("Emma only", [detection]) == [detection]

    def test_respects_word_boundaries(self) -> None:
        """A value is not matched inside a longer word."""
        detection = _detection(0, 4, "Emma")
        assert WordBoundaryExpander().expand("Emma and Emmanuel", [detection]) == [
            detection
        ]

    def test_case_insensitive_by_default(self) -> None:
        """A case variant of a detected value is found by default."""
        detection = _detection(0, 4, "Emma")
        expanded = WordBoundaryExpander().expand("Emma and emma", [detection])
        found = next(item for item in expanded if item.span == Span(9, 13))
        assert found.text == "emma"

    def test_case_sensitive_when_asked(self) -> None:
        """With case sensitivity, a case variant is not found."""
        detection = _detection(0, 4, "Emma")
        expander = WordBoundaryExpander(case_sensitive=True)
        assert expander.expand("Emma and emma", [detection]) == [detection]


class TestOverlap:
    def test_skips_an_occurrence_inside_a_kept_detection(self) -> None:
        """A value found inside a longer kept detection is already hidden."""
        text = "Monsieur Paul signe. Paul arrive."
        title = _detection(0, 13, "Monsieur Paul")
        first = _detection(21, 25, "Paul")
        expanded = WordBoundaryExpander().expand(text, [title, first])
        assert sorted(found.span for found in expanded) == [Span(0, 13), Span(21, 25)]

    def test_skips_an_occurrence_straddling_a_kept_detection(self) -> None:
        """An occurrence that only partly overlaps a kept detection is skipped."""
        text = "Paul Lemoine Immobilier. Voir Paul Lemoine."
        company = _detection(5, 23, "Lemoine Immobilier", label="ORGANIZATION")
        person = _detection(30, 42, "Paul Lemoine")
        expanded = WordBoundaryExpander().expand(text, [company, person])
        assert sorted(found.span for found in expanded) == [Span(5, 23), Span(30, 42)]

    def test_the_longer_value_claims_a_shared_occurrence(self) -> None:
        """When two values occur at one place, the longer one is added."""
        text = "Paul Lemoine et Paul. Puis Paul Lemoine."
        short = _detection(16, 20, "Paul")
        full = _detection(0, 12, "Paul Lemoine")
        expanded = WordBoundaryExpander().expand(text, [short, full])
        spans = sorted(found.span for found in expanded)
        assert spans == [Span(0, 12), Span(16, 20), Span(27, 39)]

    def test_the_result_never_overlaps_when_the_input_does_not(self) -> None:
        """Expanding disjoint detections keeps them disjoint."""
        text = "Jean Dupont, Dupont, Jean, Jean Dupont et Dupont-Martin."
        detections = [_detection(0, 11, "Jean Dupont"), _detection(13, 19, "Dupont")]
        expanded = sorted(
            WordBoundaryExpander().expand(text, detections), key=lambda d: d.span
        )
        for before, after in pairwise(expanded):
            assert before.span.end <= after.span.start
