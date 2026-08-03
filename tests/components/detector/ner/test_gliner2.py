"""Tests for the Gliner2Detector.

Conformance injects a fake model (no download); the integration test loads a
real GLiNER2 model and is marked integration. Both skip when gliner2 is absent.
"""

import pytest

from piighost.components.detector import AnyDetector


class _FakeGliner2:
    """A stand-in exposing the one method the adapter calls."""

    def extract_entities(
        self, text: str, labels: list[str], **kwargs: object
    ) -> dict[str, object]:
        return {"entities": {}}


class TestConformance:
    def test_satisfies_the_detector_port(self) -> None:
        """Gliner2Detector built on an injected model is an AnyDetector."""
        pytest.importorskip("gliner2")
        from piighost.components.detector.ner import Gliner2Detector

        detector = Gliner2Detector(model=_FakeGliner2(), labels=["PERSON"])
        assert isinstance(detector, AnyDetector)

    async def test_maps_native_labels_through_the_base(self) -> None:
        """A fake model's entities are relabeled by the base label map."""
        pytest.importorskip("gliner2")
        from piighost.components.detector.ner import Gliner2Detector

        class _Model:
            def extract_entities(
                self, text: str, labels: list[str], **kwargs: object
            ) -> dict[str, object]:
                return {
                    "entities": {
                        "person": [
                            {"text": "Emma", "start": 0, "end": 4, "confidence": 0.9}
                        ]
                    }
                }

        detector = Gliner2Detector(model=_Model(), labels={"PERSON": "person"})
        detections = await detector.detect("Emma is here")
        assert len(detections) == 1
        assert detections[0].label == "PERSON"
        assert detections[0].text == "Emma"
        assert detections[0].confidence == 0.9


@pytest.mark.integration
class TestIntegration:
    async def test_detects_a_person_with_a_real_model(self) -> None:
        """A real GLiNER2 model finds a person in a simple sentence."""
        pytest.importorskip("gliner2")
        from piighost.components.detector.ner import Gliner2Detector

        detector = Gliner2Detector(model="fastino/gliner2-multi-v1", labels=["PERSON"])
        detections = await detector.detect("My name is Patrick.")
        assert any(d.label == "PERSON" for d in detections)
