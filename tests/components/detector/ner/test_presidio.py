"""Tests for the PresidioDetector adapter.

A fake analyzer is injected, so presidio-analyzer is imported but no engine is
built and no spaCy model is downloaded; they skip when presidio is absent.
"""

import pytest

from piighost.components.detector import AnyDetector


class _Result:
    """A stand-in for a Presidio RecognizerResult."""

    def __init__(self, entity_type: str, start: int, end: int, score: float) -> None:
        self.entity_type = entity_type
        self.start = start
        self.end = end
        self.score = score


class _FakeAnalyzer:
    """A stand-in AnalyzerEngine recording its call and returning fixed results."""

    def __init__(self, results: list[_Result] | None = None) -> None:
        self._results = results or []
        self.calls: list[dict[str, object]] = []

    def analyze(
        self,
        text: str,
        language: str = "en",
        entities: list[str] | None = None,
        score_threshold: float | None = None,
    ) -> list[_Result]:
        self.calls.append(
            {
                "text": text,
                "language": language,
                "entities": entities,
                "score_threshold": score_threshold,
            }
        )
        return self._results


class TestConformance:
    def test_satisfies_the_detector_port(self) -> None:
        """A PresidioDetector on an injected analyzer is an AnyDetector."""
        pytest.importorskip("presidio_analyzer")
        from piighost.components.detector.ner import PresidioDetector

        detector = PresidioDetector(analyzer=_FakeAnalyzer())
        assert isinstance(detector, AnyDetector)


class TestDetect:
    async def test_builds_a_detection_per_result(self) -> None:
        """Each Presidio result becomes a Detection with its span text."""
        pytest.importorskip("presidio_analyzer")
        from piighost.components.detector.ner import PresidioDetector

        analyzer = _FakeAnalyzer([_Result("PERSON", 0, 4, 0.9)])
        detector = PresidioDetector(analyzer=analyzer, labels=["PERSON"])
        detections = await detector.detect("Emma is here")
        assert len(detections) == 1
        assert detections[0].label == "PERSON"
        assert detections[0].text == "Emma"
        assert detections[0].confidence == 0.9

    async def test_relabels_a_native_type_to_the_external_label(self) -> None:
        """A native PERSON type is relabeled to the mapped external label."""
        pytest.importorskip("presidio_analyzer")
        from piighost.components.detector.ner import PresidioDetector

        analyzer = _FakeAnalyzer([_Result("PERSON", 0, 4, 0.9)])
        detector = PresidioDetector(analyzer=analyzer, labels={"NAME": "PERSON"})
        detections = await detector.detect("Emma is here")
        assert len(detections) == 1
        assert detections[0].label == "NAME"

    async def test_drops_an_unmapped_type(self) -> None:
        """A native type absent from a non-empty map is dropped."""
        pytest.importorskip("presidio_analyzer")
        from piighost.components.detector.ner import PresidioDetector

        analyzer = _FakeAnalyzer([_Result("US_SSN", 0, 3, 0.9)])
        detector = PresidioDetector(analyzer=analyzer, labels={"NAME": "PERSON"})
        detections = await detector.detect("123 is here")
        assert detections == []

    async def test_passes_internal_labels_and_threshold_to_analyze(self) -> None:
        """The queried internal labels and threshold reach analyze."""
        pytest.importorskip("presidio_analyzer")
        from piighost.components.detector.ner import PresidioDetector

        analyzer = _FakeAnalyzer()
        detector = PresidioDetector(
            analyzer=analyzer, labels={"NAME": "PERSON"}, threshold=0.4
        )
        await detector.detect("Emma is here")
        assert analyzer.calls[0]["entities"] == ["PERSON"]
        assert analyzer.calls[0]["score_threshold"] == 0.4

    async def test_queries_all_entities_when_no_labels(self) -> None:
        """With no label map, analyze is asked for all entities (None)."""
        pytest.importorskip("presidio_analyzer")
        from piighost.components.detector.ner import PresidioDetector

        analyzer = _FakeAnalyzer()
        detector = PresidioDetector(analyzer=analyzer)
        await detector.detect("Emma is here")
        assert analyzer.calls[0]["entities"] is None
