"""Tests for the BaseNERDetector abstract base class."""

from __future__ import annotations

import pytest

from piighost.detector.base import BaseNERDetector
from piighost.models import Detection, Span


# ---------------------------------------------------------------------------
# Minimal concrete subclass used to exercise the base class helpers.
# ---------------------------------------------------------------------------


class StubNERDetector(BaseNERDetector):
    """Concrete subclass that echoes a fixed list of raw detections.

    Each raw detection is a tuple ``(text, raw_label, start, end, confidence)``
    representing what a model would produce. The stub applies the label
    mapping exactly as a real subclass should.
    """

    def __init__(
        self,
        labels: list[str] | dict[str, str] | None,
        raw: list[tuple[str, str, int, int, float]] | None = None,
    ) -> None:
        super().__init__(labels)
        self._raw = raw or []

    async def detect(self, text: str) -> list[Detection]:
        detections: list[Detection] = []
        for raw_text, raw_label, start, end, confidence in self._raw:
            if not self._label_map:
                label = raw_label
            else:
                mapped = self._map_label(raw_label)
                if mapped is None:
                    continue
                label = mapped
            detections.append(
                Detection(
                    text=raw_text,
                    label=label,
                    position=Span(start_pos=start, end_pos=end),
                    confidence=confidence,
                )
            )
        return detections


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_none_yields_empty_map(self):
        assert BaseNERDetector._normalize(None) == {}

    def test_empty_list_yields_empty_map(self):
        assert BaseNERDetector._normalize([]) == {}

    def test_list_becomes_identity_map(self):
        assert BaseNERDetector._normalize(["PER", "LOC"]) == {
            "PER": "PER",
            "LOC": "LOC",
        }

    def test_dict_is_copied(self):
        source = {"PERSON": "PER"}
        result = BaseNERDetector._normalize(source)
        assert result == source
        assert result is not source  # defensive copy


# ---------------------------------------------------------------------------
# Reverse lookup
# ---------------------------------------------------------------------------


class TestBuildReverse:
    def test_identity_map(self):
        reverse = BaseNERDetector._build_reverse({"PER": "PER"})
        assert reverse == {"PER": "PER"}

    def test_dict_map(self):
        reverse = BaseNERDetector._build_reverse({"PERSON": "PER", "LOCATION": "LOC"})
        assert reverse == {"PER": "PERSON", "LOC": "LOCATION"}

    def test_conflict_raises(self):
        with pytest.raises(ValueError, match="Label mapping conflict"):
            BaseNERDetector._build_reverse({"A": "x", "B": "x"})


# ---------------------------------------------------------------------------
# Instantiation & abstract contract
# ---------------------------------------------------------------------------


class TestAbstractContract:
    def test_cannot_instantiate_base_directly(self):
        with pytest.raises(TypeError):
            BaseNERDetector(labels=[])  # type: ignore[abstract]

    def test_subclass_can_instantiate(self):
        detector = StubNERDetector(labels=["PER"])
        assert isinstance(detector, BaseNERDetector)


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestProperties:
    def test_external_and_internal_labels_list_form(self):
        detector = StubNERDetector(labels=["PER", "LOC"])
        assert detector.external_labels == ["PER", "LOC"]
        assert detector.internal_labels == ["PER", "LOC"]

    def test_external_and_internal_labels_dict_form(self):
        detector = StubNERDetector(labels={"PERSON": "PER", "LOCATION": "LOC"})
        assert detector.external_labels == ["PERSON", "LOCATION"]
        assert detector.internal_labels == ["PER", "LOC"]

    def test_map_label_roundtrip(self):
        detector = StubNERDetector(labels={"PERSON": "PER"})
        assert detector._map_label("PER") == "PERSON"
        assert detector._map_label("LOC") is None


# ---------------------------------------------------------------------------
# End-to-end remapping through detect()
# ---------------------------------------------------------------------------


class TestDetectRemapping:
    @pytest.mark.asyncio
    async def test_list_form_passes_label_through(self):
        detector = StubNERDetector(
            labels=["PER"],
            raw=[("Patrick", "PER", 0, 7, 0.9)],
        )
        detections = await detector.detect("Patrick")
        assert detections[0].label == "PER"

    @pytest.mark.asyncio
    async def test_dict_form_rewrites_label(self):
        detector = StubNERDetector(
            labels={"PERSON": "PER"},
            raw=[("Patrick", "PER", 0, 7, 0.9)],
        )
        detections = await detector.detect("Patrick")
        assert len(detections) == 1
        assert detections[0].label == "PERSON"

    @pytest.mark.asyncio
    async def test_unmapped_raw_label_is_skipped(self):
        detector = StubNERDetector(
            labels={"PERSON": "PER"},
            raw=[
                ("Patrick", "PER", 0, 7, 0.9),
                ("Paris", "LOC", 18, 23, 0.8),  # not mapped → skip
            ],
        )
        detections = await detector.detect("Patrick lives in Paris")
        assert len(detections) == 1
        assert detections[0].label == "PERSON"

    @pytest.mark.asyncio
    async def test_none_labels_keeps_everything(self):
        detector = StubNERDetector(
            labels=None,
            raw=[
                ("Patrick", "PER", 0, 7, 0.9),
                ("Paris", "LOC", 18, 23, 0.8),
            ],
        )
        detections = await detector.detect("Patrick lives in Paris")
        assert {d.label for d in detections} == {"PER", "LOC"}

    @pytest.mark.asyncio
    async def test_empty_list_keeps_everything(self):
        detector = StubNERDetector(
            labels=[],
            raw=[
                ("Patrick", "PER", 0, 7, 0.9),
                ("Paris", "LOC", 18, 23, 0.8),
            ],
        )
        detections = await detector.detect("Patrick lives in Paris")
        assert {d.label for d in detections} == {"PER", "LOC"}
