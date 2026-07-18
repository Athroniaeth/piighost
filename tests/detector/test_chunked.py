"""Tests for the ChunkedDetector."""

from piighost.detector import AnyDetector, ChunkedDetector, ExactMatchDetector
from piighost.models import Span
from piighost.text import RecursiveCharacterTextSplitter


class TestConformance:
    def test_satisfies_the_detector_port(self) -> None:
        """ChunkedDetector is an AnyDetector."""
        assert isinstance(ChunkedDetector(ExactMatchDetector({})), AnyDetector)


class TestDetect:
    async def test_short_text_matches_the_inner_detector(self) -> None:
        """On text shorter than a chunk, results match the inner detector."""
        inner = ExactMatchDetector({"Emma": "PERSON"})
        chunked = ChunkedDetector(inner)
        text = "Hi Emma"
        assert await chunked.detect(text) == await inner.detect(text)

    async def test_remaps_offsets_to_the_original_text(self) -> None:
        """A value found in a later chunk points to its original position."""
        detector = ChunkedDetector(
            ExactMatchDetector({"Emma": "PERSON"}),
            RecursiveCharacterTextSplitter(chunk_size=10, chunk_overlap=5),
        )
        text = "aaaa bbbb cccc dddd Emma"
        detections = await detector.detect(text)
        assert len(detections) == 1
        span = detections[0].span
        assert text[span.start : span.end] == "Emma"
        assert span == Span(20, 24)

    async def test_deduplicates_a_value_found_in_two_chunks(self) -> None:
        """A value that falls in the overlap is reported once after dedup."""
        detector = ChunkedDetector(
            ExactMatchDetector({"bbb": "CODE"}),
            RecursiveCharacterTextSplitter(chunk_size=7, chunk_overlap=3),
        )
        detections = await detector.detect("aaa bbb ccc ddd")
        assert len(detections) == 1
        assert detections[0].span == Span(4, 7)

    async def test_finds_occurrences_across_chunks(self) -> None:
        """Every occurrence across the text is found with its original offset."""
        detector = ChunkedDetector(
            ExactMatchDetector({"xx": "CODE"}),
            RecursiveCharacterTextSplitter(chunk_size=7, chunk_overlap=3),
        )
        detections = await detector.detect("xx aa bb xx cc")
        spans = sorted(detection.span for detection in detections)
        assert spans == [Span(0, 2), Span(9, 11)]
