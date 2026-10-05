"""Tests for the RegexDetector."""

import pytest

from piighost.components.detector import AnyDetector, RegexDetector
from piighost.models import Span

IBAN = r"\b[A-Z]{2}\d{2}(?:[\s-]?[A-Z0-9]){11,30}\b"
"""An IBAN pattern written for plain spaces, as a catalog pattern is."""


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


SPACES = [
    pytest.param("\u00a0", id="no-break-space"),
    pytest.param("\u3000", id="ideographic-space"),
]
"""Two Unicode spaces standing for all of them.

test_normalization checks every separator one by one. Here two are enough to
show the component reads spaces through normalize_spaces.
"""


class TestUnicodeSpaces:
    @pytest.mark.parametrize("space", SPACES)
    async def test_a_pattern_written_for_a_space_matches_any_space(
        self, space: str
    ) -> None:
        """Any Unicode space in the value stands for the space the pattern names."""
        detector = RegexDetector({"CODE": r"\d{4}\s\d{4}"})
        detections = await detector.detect(f"code 1234{space}5678 ok")
        assert [(d.span, d.text) for d in detections] == [
            (Span(5, 14), f"1234{space}5678")
        ]

    async def test_the_detection_keeps_the_spaces_as_written(self) -> None:
        """The detected text is sliced from the original, not from the copy."""
        detector = RegexDetector({"IBAN": IBAN})
        iban = "FR76\u00a03000\u202f6000\u20070112 3456\u00a07890\u00a0189"
        (detection,) = await detector.detect(f"IBAN {iban}.")
        assert detection.text == iban

    async def test_spaces_before_a_value_do_not_shift_its_offsets(self) -> None:
        """Separators earlier in the text leave a later detection where it is."""
        text = "\u3000\u3000Mail\u00a0: a@b.co\u2028fin"
        detector = RegexDetector({"EMAIL": r"[\w.]+@[\w.]+\.\w+"})
        (detection,) = await detector.detect(text)
        assert detection.span == Span(9, 15)
        assert detection.span.extract(text) == "a@b.co"

    async def test_a_line_separator_is_read_as_a_newline(self) -> None:
        """A pattern anchored on a line boundary sees a line separator as one."""
        detector = RegexDetector({"CODE": r"(?m)^\d{4}$"})
        detections = await detector.detect("1234\u20285678")
        assert [d.text for d in detections] == ["1234", "5678"]
