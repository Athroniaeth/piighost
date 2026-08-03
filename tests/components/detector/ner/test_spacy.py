"""Tests for the SpacyDetector.

Conformance and mapping inject a fake spaCy doc (no model). The integration test
loads a real spaCy model and is marked integration. All skip when spacy absent.
"""

import pytest

from piighost.components.detector import AnyDetector


class _Ent:
    """A stand-in for a spaCy entity span."""

    def __init__(self, text: str, label: str, start_char: int, end_char: int) -> None:
        self.text = text
        self.label_ = label
        self.start_char = start_char
        self.end_char = end_char


class _Doc:
    """A stand-in for a spaCy Doc exposing ents."""

    def __init__(self, ents: list[_Ent]) -> None:
        self.ents = ents


class _FakeNlp:
    """A callable stand-in for a spaCy Language model."""

    def __init__(self, doc: _Doc) -> None:
        self._doc = doc

    def __call__(self, text: str) -> _Doc:
        return self._doc


class TestConformance:
    def test_satisfies_the_detector_port(self) -> None:
        """SpacyDetector built on an injected model is an AnyDetector."""
        pytest.importorskip("spacy")
        from piighost.components.detector.ner import SpacyDetector

        detector = SpacyDetector(model=_FakeNlp(_Doc([])))
        assert isinstance(detector, AnyDetector)


class TestDetect:
    async def test_keeps_every_entity_when_unmapped(self) -> None:
        """With no label map, every spaCy entity is kept with its native label."""
        pytest.importorskip("spacy")
        from piighost.components.detector.ner import SpacyDetector
        from piighost.models import Span

        doc = _Doc([_Ent("Emma", "PER", 0, 4)])
        detector = SpacyDetector(model=_FakeNlp(doc))
        detections = await detector.detect("Emma is here")
        assert len(detections) == 1
        assert detections[0].label == "PER"
        assert detections[0].span == Span(0, 4)
        assert detections[0].confidence == 1.0

    async def test_relabels_and_filters_with_a_map(self) -> None:
        """A label map relabels the kept entity and drops the unmapped one."""
        pytest.importorskip("spacy")
        from piighost.components.detector.ner import SpacyDetector

        doc = _Doc([_Ent("Emma", "PER", 0, 4), _Ent("here", "MISC", 8, 12)])
        detector = SpacyDetector(model=_FakeNlp(doc), labels={"PERSON": "PER"})
        detections = await detector.detect("Emma is here")
        assert [d.label for d in detections] == ["PERSON"]


@pytest.mark.integration
class TestIntegration:
    async def test_detects_a_person_with_a_real_model(self) -> None:
        """A real spaCy model finds a person in a simple sentence."""
        pytest.importorskip("spacy")
        spacy = pytest.importorskip("spacy")
        if not spacy.util.is_package("en_core_web_sm"):
            pytest.skip("en_core_web_sm model not installed")
        from piighost.components.detector.ner import SpacyDetector

        detector = SpacyDetector(model="en_core_web_sm", labels={"PERSON": "PERSON"})
        detections = await detector.detect("My name is Patrick.")
        assert any(d.label == "PERSON" for d in detections)
