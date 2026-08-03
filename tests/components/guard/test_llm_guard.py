"""Tests for the LLMGuardRail.

A fake chat model returns canned structured output, so no real LLM or network is
needed. The tests are guarded with importorskip for environments without the llm
extra, but run in the dev venv where langchain-core is installed.
"""

import pytest

from piighost.components.guard import AnyGuardRail


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
    def test_satisfies_the_port(self) -> None:
        """LLMGuardRail built on an injected model is an AnyGuardRail."""
        pytest.importorskip("langchain_core")
        from piighost.components.guard import LLMGuardRail

        model = _FakeChatModel(_FakeExtraction([]))
        assert isinstance(LLMGuardRail(model=model, labels=["PERSON"]), AnyGuardRail)


class TestCheck:
    async def test_clean_text_is_not_flagged(self) -> None:
        """When the model returns no entities, the verdict is unflagged."""
        pytest.importorskip("langchain_core")
        from piighost.components.guard import LLMGuardRail

        model = _FakeChatModel(_FakeExtraction([]))
        guard = LLMGuardRail(model=model, labels=["PERSON"])
        verdict = await guard.check("nothing to see here")
        assert verdict.flagged is False
        assert verdict.detections == ()

    async def test_residual_pii_is_flagged_and_carried(self) -> None:
        """A value the model returns and that is in the text flags the verdict."""
        pytest.importorskip("langchain_core")
        from piighost.components.guard import LLMGuardRail

        result = _FakeExtraction([_FakeEntity("Emma", "PERSON")])
        guard = LLMGuardRail(model=_FakeChatModel(result), labels=["PERSON"])
        verdict = await guard.check("Emma slipped through")
        assert verdict.flagged is True
        assert [detection.text for detection in verdict.detections] == ["Emma"]

    async def test_custom_prompt_reaches_the_model(self) -> None:
        """A custom prompt is forwarded and appears in the model's system message."""
        pytest.importorskip("langchain_core")
        from piighost.components.guard import LLMGuardRail

        captured: list[object] = []

        class _CapturingStructured:
            """A structured stand-in that records the messages it is given."""

            def __init__(self, result: object, sink: list[object]) -> None:
                self._result = result
                self._sink = sink

            async def ainvoke(self, messages: object, **kwargs: object) -> object:
                self._sink.append(messages)
                return self._result

        class _CapturingModel:
            """A chat-model stand-in whose structured output records its input."""

            def __init__(self, result: object, sink: list[object]) -> None:
                self._result = result
                self._sink = sink

            def with_structured_output(
                self, schema: object, **kwargs: object
            ) -> _CapturingStructured:
                return _CapturingStructured(self._result, self._sink)

        result = _FakeExtraction([_FakeEntity("Emma", "PERSON")])
        guard = LLMGuardRail(
            model=_CapturingModel(result, captured),
            labels=["PERSON"],
            prompt="Sentinel audit instruction for {labels}.",
        )
        verdict = await guard.check("Emma slipped through")
        assert verdict.flagged is True
        # The custom prompt reached the model as the substituted system message.
        messages = captured[0]
        system_message = messages[0]
        assert "Sentinel audit instruction" in str(system_message.content)
