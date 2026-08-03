"""Tests for the RegexDetector."""

from piighost.components.detector import AnyDetector, RegexDetector
from piighost.models import Span


class TestConformance:
    def test_satisfies_the_detector_port(self) -> None:
        """RegexDetector is an AnyDetector."""
        assert isinstance(RegexDetector({}), AnyDetector)


class TestDetect:
    async def test_finds_a_single_match_with_exact_offsets(self) -> None:
        """A pattern matching once yields one detection at the right span."""
        detector = RegexDetector({"DIGITS": r"\d+"})
        detections = await detector.detect("id 4242 ok")
        assert len(detections) == 1
        assert detections[0].span == Span(3, 7)
        assert detections[0].text == "4242"
        assert detections[0].label == "DIGITS"
        assert detections[0].confidence == 1.0

    async def test_finds_every_match_of_a_pattern(self) -> None:
        """A pattern matching several times yields one detection each."""
        detector = RegexDetector({"DIGITS": r"\d+"})
        detections = await detector.detect("1 and 22 and 333")
        spans = [detection.span for detection in detections]
        assert spans == [Span(0, 1), Span(6, 8), Span(13, 16)]

    async def test_finds_matches_for_every_label(self) -> None:
        """Each configured pattern contributes its own labeled detections."""
        detector = RegexDetector({"DIGITS": r"\d+", "WORD": r"[A-Za-z]+"})
        detections = await detector.detect("ab 12")
        found = {(detection.text, detection.label) for detection in detections}
        assert found == {("ab", "WORD"), ("12", "DIGITS")}

    async def test_empty_text_returns_empty(self) -> None:
        """Scanning empty text yields no detection."""
        detector = RegexDetector({"DIGITS": r"\d+"})
        assert await detector.detect("") == []

    async def test_no_match_returns_empty(self) -> None:
        """A text matching no pattern yields no detection."""
        detector = RegexDetector({"DIGITS": r"\d+"})
        assert await detector.detect("no numbers here") == []
