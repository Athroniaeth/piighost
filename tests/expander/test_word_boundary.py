"""Tests for the WordBoundaryExpander."""

from piighost.expander import AnyDetectionExpander, WordBoundaryExpander
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
