"""Tests for the ExactMatchDetector."""

from piighost.components.detector import AnyDetector, ExactMatchDetector
from piighost.models import Span


class TestConformance:
    def test_satisfies_the_detector_port(self) -> None:
        """ExactMatchDetector is an AnyDetector."""
        assert isinstance(ExactMatchDetector({}), AnyDetector)


class TestDetect:
    async def test_finds_a_single_occurrence(self) -> None:
        """A configured value present once yields one detection."""
        detector = ExactMatchDetector({"Emma": "PERSON"})
        detections = await detector.detect("Hi Emma!")
        assert len(detections) == 1
        assert detections[0].span == Span(3, 7)
        assert detections[0].label == "PERSON"
        assert detections[0].text == "Emma"
        assert detections[0].confidence == 1.0

    async def test_finds_every_occurrence(self) -> None:
        """A value appearing several times yields one detection each."""
        detector = ExactMatchDetector({"Emma": "PERSON"})
        detections = await detector.detect("Emma and Emma")
        spans = [detection.span for detection in detections]
        assert spans == [Span(0, 4), Span(9, 13)]

    async def test_finds_multiple_values(self) -> None:
        """Each configured value is detected with its own label."""
        detector = ExactMatchDetector({"Emma": "PERSON", "Paris": "LOCATION"})
        detections = await detector.detect("Emma in Paris")
        found = {(detection.text, detection.label) for detection in detections}
        assert found == {("Emma", "PERSON"), ("Paris", "LOCATION")}

    async def test_no_match_returns_empty(self) -> None:
        """A text without any configured value yields no detection."""
        detector = ExactMatchDetector({"Emma": "PERSON"})
        assert await detector.detect("nobody here") == []

    async def test_value_is_matched_literally_not_as_regex(self) -> None:
        """A value with regex metacharacters is matched as a literal string."""
        detector = ExactMatchDetector({"a.b": "CODE"})
        detections = await detector.detect("a.b but not axb")
        assert len(detections) == 1
        assert detections[0].span == Span(0, 3)
