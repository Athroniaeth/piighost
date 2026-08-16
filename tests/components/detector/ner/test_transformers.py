"""Tests for the TransformersDetector.

Conformance and mapping inject a fake pipeline (no download). The integration
test loads a real HF pipeline and is marked integration. All skip when
transformers is absent.
"""

import pytest

from piighost.components.detector import AnyDetector


class _FakePipeline:
    """A callable stand-in returning HF token-classification dicts."""

    def __init__(self, entities: list[dict[str, object]]) -> None:
        self._entities = entities

    def __call__(self, text: str) -> list[dict[str, object]]:
        return self._entities


class TestConformance:
    def test_satisfies_the_detector_port(self) -> None:
        """TransformersDetector built on an injected pipeline is an AnyDetector."""
        pytest.importorskip("transformers")
        from piighost.components.detector.ner import TransformersDetector

        detector = TransformersDetector(pipeline=_FakePipeline([]))
        assert isinstance(detector, AnyDetector)


class TestDetect:
    async def test_builds_detection_from_pipeline_output(self) -> None:
        """A pipeline entity becomes a Detection with span, text, confidence."""
        pytest.importorskip("transformers")
        from piighost.components.detector.ner import TransformersDetector
        from piighost.models import Span

        entities: list[dict[str, object]] = [
            {"entity_group": "PER", "score": 0.99, "start": 0, "end": 4}
        ]
        detector = TransformersDetector(pipeline=_FakePipeline(entities))
        detections = await detector.detect("Emma is here")
        assert len(detections) == 1
        assert detections[0].label == "PER"
        assert detections[0].span == Span(0, 4)
        assert detections[0].text == "Emma"
        assert detections[0].confidence == pytest.approx(0.99)

    async def test_drops_entities_below_threshold(self) -> None:
        """An entity scoring below the threshold is dropped."""
        pytest.importorskip("transformers")
        from piighost.components.detector.ner import TransformersDetector

        entities: list[dict[str, object]] = [
            {"entity_group": "PER", "score": 0.10, "start": 0, "end": 4}
        ]
        detector = TransformersDetector(pipeline=_FakePipeline(entities), threshold=0.5)
        assert await detector.detect("Emma is here") == []


@pytest.mark.integration
class TestIntegration:
    async def test_detects_a_person_with_a_real_pipeline(self) -> None:
        """A real HF NER pipeline finds a person in a simple sentence."""
        pytest.importorskip("transformers")
        from piighost.components.detector.ner import TransformersDetector

        detector = TransformersDetector(pipeline="dslim/bert-base-NER")
        detections = await detector.detect("My name is Patrick.")
        assert any(d.text for d in detections)
