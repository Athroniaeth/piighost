"""Tests for the LLMDetector.

The langchain-core extra is absent in the dev venv, so these tests skip via
importorskip. A fake chat model returns canned structured output, so no real LLM
or network is needed when the extra is present.
"""

import pytest

from piighost.components.detector import AnyDetector
from piighost.models import Span


class _FakeLabel:
    """A stand-in for a schema label enum member."""

    def __init__(self, value: str) -> None:
        self.value = value


class _FakeEntity:
    """A stand-in for one extracted entity."""

    def __init__(self, text: str, label: str) -> None:
        self.text = text
        self.label = _FakeLabel(label)


class _FakeExtraction:
    """A stand-in for the structured extraction result."""

    def __init__(self, entities: list[_FakeEntity]) -> None:
        self.entities = entities


class _FakeStructured:
    """A stand-in for model.with_structured_output(schema)."""

    def __init__(self, result: object) -> None:
        self._result = result

    async def ainvoke(self, messages: object, **kwargs: object) -> object:
        return self._result


class _FakeChatModel:
    """A stand-in chat model whose structured output is canned."""

    def __init__(self, result: object) -> None:
        self._result = result

    def with_structured_output(
        self, schema: object, **kwargs: object
    ) -> _FakeStructured:
        return _FakeStructured(self._result)


class TestConformance:
    def test_satisfies_the_detector_port(self) -> None:
        """LLMDetector built on an injected model is an AnyDetector."""
        pytest.importorskip("langchain_core")
        from piighost.components.detector import LLMDetector

        model = _FakeChatModel(_FakeExtraction([]))
        detector = LLMDetector(model=model, labels=["PERSON"])
        assert isinstance(detector, AnyDetector)


class TestDetect:
    async def test_locates_a_single_occurrence_and_relabels(self) -> None:
        """An extracted value is located and relabeled through the base map."""
        pytest.importorskip("langchain_core")
        from piighost.components.detector import LLMDetector

        result = _FakeExtraction([_FakeEntity("Emma", "person")])
        detector = LLMDetector(
            model=_FakeChatModel(result), labels={"PERSON": "person"}
        )
        detections = await detector.detect("Hi Emma!")
        assert len(detections) == 1
        assert detections[0].label == "PERSON"
        assert detections[0].span == Span(3, 7)
        assert detections[0].text == "Emma"
        assert detections[0].confidence == 1.0

    async def test_locates_every_occurrence(self) -> None:
        """A value present several times yields one detection each."""
        pytest.importorskip("langchain_core")
        from piighost.components.detector import LLMDetector

        result = _FakeExtraction([_FakeEntity("Emma", "PERSON")])
        detector = LLMDetector(model=_FakeChatModel(result), labels=["PERSON"])
        detections = await detector.detect("Emma and Emma")
        spans = [d.span for d in detections]
        assert spans == [Span(0, 4), Span(9, 13)]

    async def test_hallucinated_value_absent_from_text_is_ignored(self) -> None:
        """A value the model returned but that is not in the text yields none."""
        pytest.importorskip("langchain_core")
        from piighost.components.detector import LLMDetector

        result = _FakeExtraction([_FakeEntity("Bob", "PERSON")])
        detector = LLMDetector(model=_FakeChatModel(result), labels=["PERSON"])
        assert await detector.detect("Emma only") == []

    async def test_malformed_output_fails_open(self) -> None:
        """A result without an entities attribute yields no detection."""
        pytest.importorskip("langchain_core")
        from piighost.components.detector import LLMDetector

        detector = LLMDetector(model=_FakeChatModel(object()), labels=["PERSON"])
        assert await detector.detect("Emma only") == []

    async def test_empty_text_returns_empty(self) -> None:
        """Empty input yields no detection."""
        pytest.importorskip("langchain_core")
        from piighost.components.detector import LLMDetector

        result = _FakeExtraction([_FakeEntity("Emma", "PERSON")])
        detector = LLMDetector(model=_FakeChatModel(result), labels=["PERSON"])
        assert await detector.detect("") == []
