"""Tests for TransformersDetector using mock HF pipelines."""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Lightweight fake that mimics a HF TokenClassificationPipeline
# ---------------------------------------------------------------------------


class FakePipeline:
    """Mimics ``transformers.pipelines.token_classification.TokenClassificationPipeline``."""

    def __init__(self, results: list[dict]) -> None:
        self._results = results

    def __call__(self, text: str) -> list[dict]:
        return self._results


# ---------------------------------------------------------------------------
# Import helper – patches importlib so the guard in transformers.py passes
# even when transformers is not installed.
# ---------------------------------------------------------------------------


@pytest.fixture
def _patch_transformers(monkeypatch):
    """Make ``importlib.util.find_spec("transformers")`` return a truthy value
    and inject a fake ``transformers`` module so the detector can be imported."""
    import types
    import sys

    fake_transformers = types.ModuleType("transformers")
    fake_pipelines = types.ModuleType("transformers.pipelines")
    fake_token_cls = types.ModuleType("transformers.pipelines.token_classification")
    fake_token_cls.TokenClassificationPipeline = FakePipeline  # type: ignore[attr-defined]
    fake_pipelines.token_classification = fake_token_cls  # type: ignore[attr-defined]
    fake_transformers.pipelines = fake_pipelines  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)
    monkeypatch.setitem(sys.modules, "transformers.pipelines", fake_pipelines)
    monkeypatch.setitem(
        sys.modules,
        "transformers.pipelines.token_classification",
        fake_token_cls,
    )

    original = __import__("importlib.util").util.find_spec

    def patched_find_spec(name, *args, **kwargs):
        if name == "transformers":
            return True  # truthy sentinel
        return original(name, *args, **kwargs)

    monkeypatch.setattr("importlib.util.find_spec", patched_find_spec)


def _get_detector_class():
    """Import TransformersDetector (must be called inside a test with _patch_transformers)."""
    import importlib
    import sys

    sys.modules.pop("piighost.detector.transformers", None)
    mod = importlib.import_module("piighost.detector.transformers")
    return mod.TransformersDetector


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

TEXT = "Patrick lives in Paris"


class TestBasicMatching:
    @pytest.mark.asyncio
    async def test_single_entity(self, _patch_transformers):
        TransformersDetector = _get_detector_class()
        pipe = FakePipeline(
            [
                {
                    "entity_group": "PER",
                    "score": 0.99,
                    "word": "Patrick",
                    "start": 0,
                    "end": 7,
                },
            ]
        )
        detector = TransformersDetector(pipeline=pipe)

        detections = await detector.detect(TEXT)
        assert len(detections) == 1
        assert detections[0].text == "Patrick"
        assert detections[0].label == "PER"

    @pytest.mark.asyncio
    async def test_multiple_entities(self, _patch_transformers):
        TransformersDetector = _get_detector_class()
        pipe = FakePipeline(
            [
                {
                    "entity_group": "PER",
                    "score": 0.99,
                    "word": "Patrick",
                    "start": 0,
                    "end": 7,
                },
                {
                    "entity_group": "LOC",
                    "score": 0.95,
                    "word": "Paris",
                    "start": 17,
                    "end": 22,
                },
            ]
        )
        detector = TransformersDetector(pipeline=pipe)

        detections = await detector.detect(TEXT)
        assert len(detections) == 2

    @pytest.mark.asyncio
    async def test_no_entities(self, _patch_transformers):
        TransformersDetector = _get_detector_class()
        pipe = FakePipeline([])
        detector = TransformersDetector(pipeline=pipe)

        detections = await detector.detect("Hello world")
        assert detections == []

    @pytest.mark.asyncio
    async def test_empty_text(self, _patch_transformers):
        TransformersDetector = _get_detector_class()
        pipe = FakePipeline([])
        detector = TransformersDetector(pipeline=pipe)

        detections = await detector.detect("")
        assert detections == []

    @pytest.mark.asyncio
    async def test_entity_key_fallback(self, _patch_transformers):
        """When ``entity_group`` is absent, fall back to ``entity``."""
        TransformersDetector = _get_detector_class()
        pipe = FakePipeline(
            [
                {
                    "entity": "B-PER",
                    "score": 0.90,
                    "word": "Patrick",
                    "start": 0,
                    "end": 7,
                },
            ]
        )
        detector = TransformersDetector(pipeline=pipe)

        detections = await detector.detect(TEXT)
        assert detections[0].label == "B-PER"


class TestLabelFiltering:
    @pytest.mark.asyncio
    async def test_filters_by_label(self, _patch_transformers):
        TransformersDetector = _get_detector_class()
        pipe = FakePipeline(
            [
                {
                    "entity_group": "PER",
                    "score": 0.99,
                    "word": "Patrick",
                    "start": 0,
                    "end": 7,
                },
                {
                    "entity_group": "LOC",
                    "score": 0.95,
                    "word": "Paris",
                    "start": 17,
                    "end": 22,
                },
            ]
        )
        detector = TransformersDetector(pipeline=pipe, labels=["PER"])

        detections = await detector.detect(TEXT)
        assert len(detections) == 1
        assert detections[0].label == "PER"

    @pytest.mark.asyncio
    async def test_no_label_filter_keeps_all(self, _patch_transformers):
        TransformersDetector = _get_detector_class()
        pipe = FakePipeline(
            [
                {
                    "entity_group": "PER",
                    "score": 0.99,
                    "word": "Patrick",
                    "start": 0,
                    "end": 7,
                },
                {
                    "entity_group": "LOC",
                    "score": 0.95,
                    "word": "Paris",
                    "start": 17,
                    "end": 22,
                },
            ]
        )
        detector = TransformersDetector(pipeline=pipe, labels=None)

        detections = await detector.detect(TEXT)
        assert len(detections) == 2


class TestDetectionAttributes:
    @pytest.mark.asyncio
    async def test_confidence_from_score(self, _patch_transformers):
        TransformersDetector = _get_detector_class()
        pipe = FakePipeline(
            [
                {
                    "entity_group": "PER",
                    "score": 0.9876,
                    "word": "Patrick",
                    "start": 0,
                    "end": 7,
                },
            ]
        )
        detector = TransformersDetector(pipeline=pipe)

        detections = await detector.detect(TEXT)
        assert detections[0].confidence == pytest.approx(0.9876)

    @pytest.mark.asyncio
    async def test_positions_are_correct(self, _patch_transformers):
        TransformersDetector = _get_detector_class()
        pipe = FakePipeline(
            [
                {
                    "entity_group": "LOC",
                    "score": 0.95,
                    "word": "Paris",
                    "start": 17,
                    "end": 22,
                },
            ]
        )
        detector = TransformersDetector(pipeline=pipe)

        detections = await detector.detect(TEXT)
        assert detections[0].position.start_pos == 17
        assert detections[0].position.end_pos == 22

    @pytest.mark.asyncio
    async def test_text_from_offsets(self, _patch_transformers):
        """Text is extracted via offsets, not from ``word`` (avoids tokenizer artifacts)."""
        TransformersDetector = _get_detector_class()
        pipe = FakePipeline(
            [
                {
                    "entity_group": "PER",
                    "score": 0.99,
                    "word": "Pat ##rick",
                    "start": 0,
                    "end": 7,
                },
            ]
        )
        detector = TransformersDetector(pipeline=pipe)

        detections = await detector.detect(TEXT)
        assert detections[0].text == "Patrick"
