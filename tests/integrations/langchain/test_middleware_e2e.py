"""End-to-end middleware tests over a real create_agent run.

These exercise the middleware through an actual LangGraph agent loop with a fake
chat model, so a bug that only shows across turns, such as clear PII persisting in
an AIMessage's tool_calls into the next model call, is caught where the unit tests
with a hand-built ToolCallRequest cannot see it.
"""

import re
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from piighost.components.detector import ExactMatchDetector
from piighost.components.entity_resolver import MergeEntityResolver
from piighost.integrations.langchain import PIIAnonymizationMiddleware
from piighost.models import Detection, Span
from piighost.pipeline import ThreadAnonymizationPipeline

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


_TOKEN = re.compile(r"<<[A-Z_]+:\d+>>")
"""A label-counter token, as the model reads and writes it."""

_COPY: dict[str, Any] = {"seen": [], "dms": []}
"""What the copying model saw at each call, and who each DM reached."""


class _ContextNer:
    """A NER stand-in: Florence is a city where someone lives, a first name otherwise."""

    async def detect(self, text: str) -> list[Detection]:
        """Find every Florence, Paul and Marc, labelling Florence by its context."""
        found = []
        for value in ("Florence", "Paul", "Marc"):
            for match in re.finditer(value, text):
                city = value == "Florence" and "habite" in text
                span = Span(match.start(), match.end())
                detection = Detection(
                    span=span,
                    text=value,
                    label="LOCATION" if city else "PERSON",
                    confidence=0.9,
                )
                found.append(detection)
        return found


class _CopyingModel(BaseChatModel):
    """A model that sees only tokens and copies the one it reads, as an LLM does."""

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        _COPY["seen"].append([m.model_copy(deep=True) for m in messages])
        step = len(_COPY["seen"])
        if step == 1:
            asked = _TOKEN.findall(str(messages[-1].content))[-1]
            msg = _tool_call("ask", {"person": asked, "question": "Tu viens ?"})
        elif step == 3:
            msg = _tool_call("read_inbox", {})
        elif step == 4:
            answer = next(m for m in messages if isinstance(m, ToolMessage))
            confirmed = _TOKEN.findall(str(answer.content))[0]
            msg = _tool_call("send_dm", {"to": confirmed, "text": "Merci !"})
        else:
            msg = AIMessage(content="C'est fait.")
        return ChatResult(generations=[ChatGeneration(message=msg)])

    @property
    def _llm_type(self) -> str:
        return "fake"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "BaseChatModel":
        return self


def _tool_call(name: str, args: dict[str, str]) -> AIMessage:
    """Build an assistant message calling one tool."""
    call = {"name": name, "id": name, "type": "tool_call", "args": args}
    return AIMessage(content="", tool_calls=[call])


@tool
def ask(person: str, question: str) -> str:
    """Ask someone a question and return the answer."""
    return f"{person} répond : oui, je viens samedi."


@tool
def read_inbox() -> str:
    """Read the last mail received."""
    return "Florence : bien reçu ton message, à samedi."


@tool
def send_dm(to: str, text: str) -> str:
    """Send a private message."""
    _COPY["dms"].append(to)
    return "envoyé"


async def test_a_token_kept_in_a_tool_result_still_names_its_person() -> None:
    """A later message relabelling a value never sends a DM to another person."""
    _COPY["seen"], _COPY["dms"] = [], []
    pipeline = ThreadAnonymizationPipeline(
        _ContextNer(),
        entity_resolver=MergeEntityResolver(),
    )
    agent = create_agent(
        model=_CopyingModel(),
        tools=[ask, read_inbox, send_dm],
        middleware=[PIIAnonymizationMiddleware(pipeline)],
        checkpointer=InMemorySaver(),
    )
    config: Any = {"configurable": {"thread_id": "t1"}}
    first = "J'habite à Florence. Paul et Marc arrivent, demande à Paul s'il vient."
    second = "Lis mes mails, puis remercie celui qui a confirmé."

    await agent.ainvoke({"messages": [HumanMessage(first)]}, config=config)
    await agent.ainvoke({"messages": [HumanMessage(second)]}, config=config)

    assert _COPY["dms"] == ["Paul"]


async def test_a_tool_call_the_model_wrote_stays_intact() -> None:
    """The model reads its own earlier tool call with its token unbroken."""
    _COPY["seen"], _COPY["dms"] = [], []
    pipeline = ThreadAnonymizationPipeline(_ContextNer())
    agent = create_agent(
        model=_CopyingModel(),
        tools=[ask, read_inbox, send_dm],
        middleware=[PIIAnonymizationMiddleware(pipeline)],
    )
    first = "J'habite à Florence. Paul et Marc arrivent, demande à Paul s'il vient."

    await agent.ainvoke(
        {"messages": [HumanMessage(first)]},
        config={"configurable": {"thread_id": "t1"}},
    )

    second_call = _COPY["seen"][1]
    call = next(m for m in second_call if isinstance(m, AIMessage) and m.tool_calls)
    assert _TOKEN.fullmatch(call.tool_calls[0]["args"]["person"])
