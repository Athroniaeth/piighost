"""Tests for the LLMGuardRail.

A fake chat model returns canned structured output, so no real LLM or network is
needed. langchain-core comes with the dev group, so the tests always run.
"""

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

from piighost.components.guard import AnyGuardRail

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import BaseMessage


def _extraction(*entities: tuple[str, str]) -> SimpleNamespace:
    """Build a stand-in structured extraction result from (text, label) pairs."""
    found = [
        SimpleNamespace(text=text, label=SimpleNamespace(value=label))
        for text, label in entities
    ]
    return SimpleNamespace(entities=found)


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


def _as_model(fake: object) -> "BaseChatModel":
    """Type a stand-in as the chat model it imitates, for the guard's signature."""
    return cast("BaseChatModel", fake)


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """LLMGuardRail built on an injected model is an AnyGuardRail."""
        from piighost.components.guard import LLMGuardRail

        model = _CapturingModel(_extraction(), [])
        assert isinstance(
            LLMGuardRail(model=_as_model(model), labels=["PERSON"]), AnyGuardRail
        )


class TestCheck:
    async def test_clean_text_is_not_flagged(self) -> None:
        """When the model returns no entities, the verdict is unflagged."""
        from piighost.components.guard import LLMGuardRail

        model = _CapturingModel(_extraction(), [])
        guard = LLMGuardRail(model=_as_model(model), labels=["PERSON"])
        verdict = await guard.check("nothing to see here")
        assert verdict.flagged is False
        assert verdict.detections == ()

    async def test_residual_pii_is_flagged_and_carried(self) -> None:
        """A value the model returns and that is in the text flags the verdict."""
        from piighost.components.guard import LLMGuardRail

        result = _extraction(("Emma", "PERSON"))
        guard = LLMGuardRail(
            model=_as_model(_CapturingModel(result, [])), labels=["PERSON"]
        )
        verdict = await guard.check("Emma slipped through")
        assert verdict.flagged is True
        assert [detection.text for detection in verdict.detections] == ["Emma"]

    async def test_custom_prompt_reaches_the_model(self) -> None:
        """A custom prompt is forwarded and appears in the model's system message."""
        from piighost.components.guard import LLMGuardRail

        captured: list[object] = []
        result = _extraction(("Emma", "PERSON"))
        guard = LLMGuardRail(
            model=_as_model(_CapturingModel(result, captured)),
            labels=["PERSON"],
            prompt="Sentinel audit instruction for {labels}.",
        )
        verdict = await guard.check("Emma slipped through")
        assert verdict.flagged is True
        # The custom prompt reached the model as the substituted system message.
        messages = cast("list[BaseMessage]", captured[0])
        system_message = messages[0]
        assert "Sentinel audit instruction" in str(system_message.content)

    async def test_placeholder_hint_follows_custom_delimiters(self) -> None:
        """The default prompt's placeholder examples match the given delimiters."""
        from piighost.components.guard import LLMGuardRail

        captured: list[object] = []
        guard = LLMGuardRail(
            model=_as_model(_CapturingModel(_extraction(), captured)),
            labels=["PERSON"],
            prefix="[[",
            suffix="]]",
        )
        await guard.check("check this")
        messages = cast("list[BaseMessage]", captured[0])
        system_prompt = str(messages[0].content)
        assert "[[PERSON:1]]" in system_prompt
        assert "<<PERSON:1>>" not in system_prompt
