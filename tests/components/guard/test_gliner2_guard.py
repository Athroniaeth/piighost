"""Tests for the Gliner2GuardRail.

The model is injected, so no weights are downloaded and the tests run without
a network; they skip when gliner2 is absent.
"""

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from piighost.components.guard.gliner2 import Gliner2GuardRail


class _FakeGliner2:
    """A stand-in answering the one classification the guard asks for."""

    def __init__(self, label: str, confidence: float) -> None:
        self.label = label
        self.confidence = confidence
        self.asked: dict[str, list[str]] | None = None

    def classify_text(
        self, text: str, tasks: dict[str, list[str]], **kwargs: object
    ) -> dict[str, dict[str, object]]:
        self.asked = tasks
        task = next(iter(tasks))
        return {task: {"label": self.label, "confidence": self.confidence}}


def _guard(label: str, confidence: float, threshold: float = 0.5) -> "Gliner2GuardRail":
    """Build a guard over a fake model answering a fixed verdict."""
    from piighost.components.guard import Gliner2GuardRail

    return Gliner2GuardRail(model=_FakeGliner2(label, confidence), threshold=threshold)


class TestUsableWhenInstalled:
    def test_conforms_to_the_port(self) -> None:
        """With gliner2 installed, Gliner2GuardRail is an AnyGuardRail."""
        pytest.importorskip("gliner2")
        from piighost.components.guard import AnyGuardRail

        assert isinstance(_guard("safe", 0.9), AnyGuardRail)

    async def test_flags_an_unsafe_answer_above_the_threshold(self) -> None:
        """An unsafe answer the model is confident about flags the verdict."""
        pytest.importorskip("gliner2")
        verdict = await _guard("unsafe", 0.99).check("John Doe lives in Paris")
        assert verdict.flagged is True
        assert verdict.score == 0.99

    async def test_does_not_flag_a_safe_answer(self) -> None:
        """A safe answer leaves the verdict unflagged, however confident."""
        pytest.importorskip("gliner2")
        verdict = await _guard("safe", 0.99).check("<<PERSON:1>> lives in Paris")
        assert verdict.flagged is False

    async def test_an_unsure_unsafe_answer_does_not_flag(self) -> None:
        """Below the threshold the guard lets the text through rather than guess."""
        pytest.importorskip("gliner2")
        verdict = await _guard("unsafe", 0.3, threshold=0.5).check("maybe")
        assert verdict.flagged is False
        assert verdict.score == 0.3

    async def test_asks_the_response_safety_task_by_default(self) -> None:
        """A guard runs on what the pipeline returns, which is a response."""
        pytest.importorskip("gliner2")
        from piighost.components.guard import Gliner2GuardRail

        model = _FakeGliner2("safe", 0.9)
        await Gliner2GuardRail(model=model).check("text")
        assert model.asked == {"response_safety": ["safe", "unsafe"]}

    async def test_the_task_and_its_labels_are_configurable(self) -> None:
        """Another task of the same model is read the same way."""
        pytest.importorskip("gliner2")
        from piighost.components.guard import Gliner2GuardRail

        model = _FakeGliner2("compliance", 0.8)
        guard = Gliner2GuardRail(
            model=model, task="response_refusal", labels=("compliance", "refusal")
        )
        verdict = await guard.check("text")
        assert model.asked == {"response_refusal": ["compliance", "refusal"]}
        assert verdict.flagged is False
