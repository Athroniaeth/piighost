"""Tests for the Presidio detector config.

The AnalyzerEngine is faked via monkeypatch, so build() constructs no real
engine and downloads no spaCy model; they skip when presidio is absent.
"""

import pytest


class _FakeEngine:
    """A stand-in AnalyzerEngine that records construction."""


def test_builds_a_presidio_detector(monkeypatch: pytest.MonkeyPatch) -> None:
    """The config wires labels, language, and threshold into a PresidioDetector."""
    pytest.importorskip("presidio_analyzer")
    monkeypatch.setattr(
        "piighost.components.detector.ner.presidio.AnalyzerEngine", _FakeEngine
    )

    from piighost.components.detector.ner import PresidioDetector
    from piighost.config.models.detector_model import PresidioDetectorConfig

    config = PresidioDetectorConfig(
        type="presidio",
        labels={"NAME": "PERSON"},
        language="en",
        threshold=0.3,
    )
    detector = config.build()

    assert isinstance(detector, PresidioDetector)
    assert isinstance(detector.analyzer, _FakeEngine)
    assert detector.language == "en"
    assert detector.threshold == 0.3
    assert detector.external_labels == ["NAME"]


def test_defaults_language_and_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    """Language defaults to en and threshold to 0.0 when omitted."""
    pytest.importorskip("presidio_analyzer")
    monkeypatch.setattr(
        "piighost.components.detector.ner.presidio.AnalyzerEngine", _FakeEngine
    )

    from piighost.components.detector.ner import PresidioDetector
    from piighost.config.models.detector_model import PresidioDetectorConfig

    config = PresidioDetectorConfig(type="presidio")
    detector = config.build()

    assert isinstance(detector, PresidioDetector)
    assert detector.language == "en"
    assert detector.threshold == 0.0
