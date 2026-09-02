"""End-to-end middleware tests over a real create_agent run.

These exercise the middleware through an actual LangGraph agent loop with a fake
chat model, so a bug that only shows across turns, such as clear PII persisting in
an AIMessage's tool_calls into the next model call, is caught where the unit tests
with a hand-built ToolCallRequest cannot see it.
"""

from typing import Any

import pytest

from piighost.components.detector import ExactMatchDetector
from piighost.integrations.langchain import PIIAnonymizationMiddleware
from piighost.pipeline import ThreadAnonymizationPipeline

pytest.importorskip("langchain")

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool

# Recording state lives outside the pydantic model, so the fake stays a plain
# BaseChatModel with no mutable-field surprises. Reset it at the start of a test.
_STATE: dict[str, Any] = {"seen": [], "calls": 0}
_RECEIVED: dict[str, str] = {}


class _RecordingModel(BaseChatModel):
    """Return a tool call on the first turn, text on the second; record prompts."""

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        _STATE["seen"].append([m.model_copy(deep=True) for m in messages])
        _STATE["calls"] += 1
        if _STATE["calls"] == 1:
            msg = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "send_mail",
                        "id": "c1",
                        "type": "tool_call",
                        "args": {"to": "<<EMAIL:1>>", "body": "hi <<PERSON:1>>"},
                    }
                ],
            )
        else:
            msg = AIMessage(content="Done, mail sent to <<PERSON:1>>.")
        return ChatResult(generations=[ChatGeneration(message=msg)])

    @property
    def _llm_type(self) -> str:
        return "fake"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "BaseChatModel":
        return self


@tool
def send_mail(to: str, body: str) -> str:
    """Send a mail."""
    _RECEIVED["to"], _RECEIVED["body"] = to, body
    return f"sent to {to}"


async def test_second_model_call_never_sees_clear_tool_args() -> None:
    """The tool gets real values; the next model call sees only tokens."""
    _STATE["seen"], _STATE["calls"] = [], 0
    _RECEIVED.clear()

    detector = ExactMatchDetector(
        {"Patrick Dupont": "PERSON", "patrick@acme.com": "EMAIL"}
    )
    pipeline = ThreadAnonymizationPipeline(detector)
    middleware = PIIAnonymizationMiddleware(pipeline)
    model = _RecordingModel()
    agent = create_agent(model=model, tools=[send_mail], middleware=[middleware])

    await agent.ainvoke(
        {"messages": [HumanMessage("Mail Patrick Dupont at patrick@acme.com")]},
        config={"configurable": {"thread_id": "t1"}},
    )

    # The tool ran on the real values.
    assert _RECEIVED == {"to": "patrick@acme.com", "body": "hi Patrick Dupont"}

    # The second model call saw no clear PII anywhere, tool_calls included.
    second_call = _STATE["seen"][1]
    dumped = " ".join(repr(m) for m in second_call)
    assert "patrick@acme.com" not in dumped
    assert "Patrick Dupont" not in dumped
