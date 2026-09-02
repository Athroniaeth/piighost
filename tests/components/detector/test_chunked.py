"""Tests for the ChunkedDetector."""

import asyncio

from piighost.components.detector import (
    AnyDetector,
    ChunkedDetector,
    ExactMatchDetector,
)
from piighost.models import Detection, Span
from piighost.text import RecursiveCharacterTextSplitter


class _ConcurrencyProbe:
    """A detector recording the peak number of overlapping detect calls."""

    def __init__(self) -> None:
        self.current = 0
        self.peak = 0

    async def detect(self, text: str) -> list[Detection]:
        """Track concurrency across a yield point, returning no detections."""
        self.current += 1
        self.peak = max(self.peak, self.current)
        await asyncio.sleep(0)
        self.current -= 1
        return []


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


class TestConcurrency:
    async def test_chunks_are_scanned_concurrently(self) -> None:
        """Several chunks overlap in flight rather than running one after another."""
        probe = _ConcurrencyProbe()
        detector = ChunkedDetector(
            probe, RecursiveCharacterTextSplitter(chunk_size=10, chunk_overlap=2)
        )
        await detector.detect("aaaa bbbb cccc dddd eeee ffff gggg")
        assert probe.peak > 1
