"""Tests for the BaseNERDetector Template Method.

A fake subclass supplies canned raw detections so the shared label-mapping and
filtering logic is exercised without loading any model.
"""

import pytest

from piighost.components.detector import AnyDetector
from piighost.components.detector.ner import BaseNERDetector
from piighost.exceptions import LabelMappingError
from piighost.models import Detection, Span


class _FakeNERDetector(BaseNERDetector):
    """A BaseNERDetector whose raw detections are injected, no model."""

    def __init__(self, raw, labels=None, max_concurrency=None):
        super().__init__(labels, max_concurrency=max_concurrency)
        self._raw = raw

    async def _raw_detect(self, text: str) -> list[Detection]:
        return self._raw


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


class TestRunBlocking:
    async def test_runs_a_blocking_callable_off_the_loop(self) -> None:
        """_run_blocking returns the callable's result."""
        detector = _FakeNERDetector([])
        assert await detector._run_blocking(lambda value: value * 2, 21) == 42

    async def test_bounded_run_blocking_still_returns(self) -> None:
        """With max_concurrency set, the semaphore path still returns."""
        detector = _FakeNERDetector([], max_concurrency=1)
        assert await detector._run_blocking(lambda value: value + 1, 41) == 42
