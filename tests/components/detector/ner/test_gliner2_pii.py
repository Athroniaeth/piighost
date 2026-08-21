"""Tests for the Gliner2PiiDetector preset.

Conformance and preset checks inject a fake model, so no weights are downloaded;
they skip when gliner2 is absent.
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
        """Gliner2PiiDetector on an injected model is an AnyDetector, no download."""
        pytest.importorskip("gliner2")
        from piighost.components.detector.ner import Gliner2PiiDetector

        detector = Gliner2PiiDetector(model=_FakeGliner2())
        assert isinstance(detector, AnyDetector)


class TestPreset:
    def test_presets_the_pii_label_set(self) -> None:
        """The default labels cover the PII taxonomy without being passed."""
        pytest.importorskip("gliner2")
        from piighost.components.detector.ner import Gliner2PiiDetector

        detector = Gliner2PiiDetector(model=_FakeGliner2())
        assert "PERSON" in detector.external_labels
        assert "CREDIT_CARD" in detector.external_labels
        assert "person" in detector.internal_labels

    async def test_relabels_a_native_entity_to_the_preset_label(self) -> None:
        """A native 'person' entity is relabeled to the preset PERSON label."""
        pytest.importorskip("gliner2")
        from piighost.components.detector.ner import Gliner2PiiDetector

        class _Model:
            def extract_entities(
                self, text: str, labels: list[str], **kwargs: object
            ) -> dict[str, object]:
                entity = {"text": "Emma", "start": 0, "end": 4, "confidence": 0.9}
                return {"entities": {"person": [entity]}}

        detector = Gliner2PiiDetector(model=_Model())
        detections = await detector.detect("Emma is here")
        assert len(detections) == 1
        assert detections[0].label == "PERSON"

    def test_labels_can_be_overridden(self) -> None:
        """Passing labels replaces the preset default."""
        pytest.importorskip("gliner2")
        from piighost.components.detector.ner import Gliner2PiiDetector

        detector = Gliner2PiiDetector(model=_FakeGliner2(), labels=["EMAIL"])
        assert detector.external_labels == ["EMAIL"]
