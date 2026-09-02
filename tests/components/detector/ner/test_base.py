"""Tests for the BaseNERDetector Template Method.

A fake subclass supplies canned raw detections so the shared label-mapping and
filtering logic is exercised without loading any model.
"""

import pytest

from piighost.components.detector import AnyDetector
from piighost.components.detector.ner import BaseNERDetector
from piighost.exceptions import LabelMappingError, TextTooLongError
from piighost.models import Detection, Span
from piighost.text import find_all_word_boundary


class _FakeNERDetector(BaseNERDetector):
    """A BaseNERDetector whose raw detections are injected, no model."""

    def __init__(
        self,
        raw: list[Detection],
        labels: list[str] | dict[str, str] | None = None,
        max_concurrency: int | None = None,
    ) -> None:
        super().__init__(labels, max_concurrency=max_concurrency)
        self._raw = raw

    async def _raw_detect(self, text: str) -> list[Detection]:
        return self._raw


class _MarkerNERDetector(BaseNERDetector):
    """A BaseNERDetector that flags a marker word, recording each text seen.

    It detects the marker at its offset within whatever text it is handed, so a
    test can check both that a long text was chunked and that the resulting spans
    are remapped back onto the original text.
    """

    def __init__(self, marker: str = "SECRET", **kwargs: object) -> None:
        super().__init__(None, **kwargs)  # type: ignore[arg-type]
        self._marker = marker
        self.seen: list[str] = []

    async def _raw_detect(self, text: str) -> list[Detection]:
        self.seen.append(text)
        return [
            Detection(span=span, text=self._marker, label="PERSON", confidence=0.9)
            for span in find_all_word_boundary(text, self._marker, 0)
        ]


def _det(label: str, confidence: float = 0.9) -> Detection:
    """Build a Detection at a fixed span for a native label."""
    return Detection(span=Span(0, 4), text="Emma", label=label, confidence=confidence)


class TestConformance:
    def test_satisfies_the_detector_port(self) -> None:
        """A BaseNERDetector subclass is an AnyDetector."""
        assert isinstance(_FakeNERDetector([]), AnyDetector)


class TestLabelMapping:
    async def test_identity_list_keeps_mapped_and_drops_the_rest(self) -> None:
        """A list maps labels to themselves and drops any not listed."""
        detector = _FakeNERDetector([_det("PERSON"), _det("ORG")], labels=["PERSON"])
        detections = await detector.detect("Emma")
        assert [d.label for d in detections] == ["PERSON"]

    async def test_dict_relabels_native_to_external(self) -> None:
        """A dict rewrites the native label to its external label."""
        detector = _FakeNERDetector([_det("PER")], labels={"PERSON": "PER"})
        detections = await detector.detect("Emma")
        assert len(detections) == 1
        assert detections[0].label == "PERSON"
        assert detections[0].span == Span(0, 4)
        assert detections[0].confidence == 0.9

    async def test_dict_drops_unmapped_native_labels(self) -> None:
        """With a non-empty map, an unmapped native label is dropped."""
        detector = _FakeNERDetector([_det("LOC")], labels={"PERSON": "PER"})
        assert await detector.detect("Emma") == []

    async def test_empty_map_keeps_every_native_label(self) -> None:
        """With no map, every detection is kept with its native label."""
        detector = _FakeNERDetector([_det("PER"), _det("WHATEVER")])
        labels = [d.label for d in await detector.detect("Emma")]
        assert labels == ["PER", "WHATEVER"]

    def test_ambiguous_reverse_map_is_refused(self) -> None:
        """Two external labels for one internal label raise LabelMappingError."""
        with pytest.raises(LabelMappingError, match="conflict"):
            _FakeNERDetector([], labels={"PERSON": "X", "COMPANY": "X"})

    def test_internal_and_external_labels(self) -> None:
        """internal_labels are the map values, external_labels the keys."""
        detector = _FakeNERDetector([], labels={"PERSON": "per", "COMPANY": "org"})
        assert detector.internal_labels == ["per", "org"]
        assert detector.external_labels == ["PERSON", "COMPANY"]


class TestMaxChars:
    async def test_short_text_is_not_chunked(self) -> None:
        """A text within max_chars is scanned whole, in one pass."""
        detector = _MarkerNERDetector(max_chars=1000)
        await detector.detect("a short SECRET here")
        assert detector.seen == ["a short SECRET here"]

    async def test_long_text_is_chunked_and_offsets_remapped(self) -> None:
        """A text over max_chars is chunked, and spans map back to the original."""
        detector = _MarkerNERDetector(max_chars=20, auto_chunk=True)
        text = ("filler word " * 8) + "SECRET"
        detections = await detector.detect(text)
        assert len(detector.seen) > 1
        assert len(detections) == 1
        span = detections[0].span
        assert text[span.start : span.end] == "SECRET"

    async def test_long_text_raises_when_auto_chunk_is_off(self) -> None:
        """Over max_chars with chunking off fails closed rather than truncate."""
        detector = _MarkerNERDetector(max_chars=20, auto_chunk=False)
        with pytest.raises(TextTooLongError):
            await detector.detect("x " * 100)

    async def test_no_limit_by_default(self) -> None:
        """Without max_chars, a long text is scanned whole."""
        detector = _MarkerNERDetector()
        text = "z " * 500 + "SECRET"
        await detector.detect(text)
        assert detector.seen == [text]


class TestRunBlocking:
    async def test_runs_a_blocking_callable_off_the_loop(self) -> None:
        """_run_blocking returns the callable's result."""
        detector = _FakeNERDetector([])
        assert await detector._run_blocking(lambda value: value * 2, 21) == 42

    async def test_bounded_run_blocking_still_returns(self) -> None:
        """With max_concurrency set, the semaphore path still returns."""
        detector = _FakeNERDetector([], max_concurrency=1)
        assert await detector._run_blocking(lambda value: value + 1, 41) == 42
