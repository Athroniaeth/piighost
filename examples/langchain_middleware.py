# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost[middleware]"]
#
# [tool.uv.sources]
# piighost = { path = "..", editable = true }
# ///
"""Run a LangChain agent behind the PII anonymization middleware.

The middleware sits around the model and tool boundary of a LangGraph agent. It
anonymizes every message before the model sees it, deanonymizes the model's
reply for the user, and routes tool calls by a strategy. With the FULL strategy
a tool receives the real value (its arguments are deanonymized) and its result
is re-anonymized before the model sees it, so the model only ever handles
placeholders while the tool works on the plain value.

To keep the example runnable without an API key, the model is a scripted fake
that returns a fixed tool call then a fixed reply, and a capture list records
what the model actually received. Run with:
uv run examples/langchain_middleware.py
"""

import asyncio
from typing import Any, Self

from langchain.agents import create_agent
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatResult
from langchain_core.tools import tool

from piighost.components.anonymizer import Anonymizer
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.pipeline import ThreadAnonymizationPipeline
from piighost.components.placeholder import (
    LabelCounterPlaceholderFactory,
    PreservesLabeledIdentityOpaque,
)
from piighost.integrations.middleware import (
    PIIAnonymizationMiddleware,
    ToolCallStrategy,
)

# The messages the model was given on each call. It lets the example show that
# the model only ever saw placeholders; a real model needs nothing like it.
MODEL_INPUTS: list[list[str]] = []


class ScriptedChatModel(GenericFakeChatModel):
    """A deterministic fake model that returns preset messages, no API key.

    It stands in for a real chat model so the example runs offline. bind_tools
    is a no-op because the scripted replies already carry the tool call, and
    _generate records what the model was asked before answering.
    """

    def bind_tools(self, tools: Any, **kwargs: Any) -> Self:
        """Ignore tool binding, the scripted replies drive the agent."""
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Record the non-empty message contents, then return the next script."""
        MODEL_INPUTS.append(
            [str(message.content) for message in messages if message.content]
        )
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


@tool
def book_slot(person: str) -> str:
    """Book a ten o'clock slot for a person and echo who it was for."""
    return f"Booked a 10:00 slot for {person}."


def _build_pipeline() -> ThreadAnonymizationPipeline[PreservesLabeledIdentityOpaque]:
    """Wire a thread pipeline whose tokens preserve identity, as the middleware needs."""
    ph_factory = LabelCounterPlaceholderFactory()
    return ThreadAnonymizationPipeline(
        ExactMatchDetector({"Emma": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(ph_factory),
        InMemoryConversationMemory(),
    )


def _build_agent() -> Any:
    """Attach the middleware to an agent driven by the scripted model and tool."""
    pipeline = _build_pipeline()
    middleware = PIIAnonymizationMiddleware(
        pipeline, tool_strategy=ToolCallStrategy.FULL
    )
    script = iter(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "book_slot",
                        "args": {"person": "<<PERSON:1>>"},
                        "id": "c1",
                    }
                ],
            ),
            AIMessage(content="All set, <<PERSON:1>>."),
        ]
    )
    model = ScriptedChatModel(messages=script)
    return create_agent(model=model, tools=[book_slot], middleware=[middleware])


async def main() -> None:
    """Run one agent turn and show anonymization at the model and tool boundary."""
    agent = _build_agent()

    request = {"messages": [HumanMessage("Book a slot for Emma.")]}
    config = {"configurable": {"thread_id": "t1"}}
    result = await agent.ainvoke(request, config=config)

    print("== what the model received (placeholders only) ==")
    for turn, seen in enumerate(MODEL_INPUTS, start=1):
        print(f"  call {turn}: {seen}")

    print("\n== the tool boundary (FULL strategy) ==")
    for message in result["messages"]:
        if isinstance(message, AIMessage) and message.tool_calls:
            args = message.tool_calls[0]["args"]
            print(f"  tool call args, deanonymized for the tool: {args}")
        if isinstance(message, ToolMessage):
            print(f"  tool result, re-anonymized for the model:  {message.content!r}")

    print("\n== what the user sees (deanonymized) ==")
    print(f"  {result['messages'][-1].content!r}")


if __name__ == "__main__":
    asyncio.run(main())
