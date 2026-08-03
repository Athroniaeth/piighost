# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost[middleware]"]
#
# [tool.uv.sources]
# piighost = { path = "../..", editable = true }
# ///
"""Contrast the four tool-call strategies of the middleware.

A tool call has two boundaries the middleware can act on. Inbound, the tool's
arguments can be deanonymized so the tool works on the real value. Outbound, the
tool's result can be re-anonymized so the model only sees placeholders. Each
ToolCallStrategy picks which boundaries are handled:

  FULL         deanonymize the arguments and re-anonymize the result
  INPUT        deanonymize the arguments only, the result is anonymized later
               by the normal before-model pass
  OUTPUT       re-anonymize the result only, the tool sees placeholders
  PASSTHROUGH  neither, the tool call is untouched

The scenario is the same each time. The model calls lookup_manager with the
person placeholder, and the tool returns a sentence naming a second person,
Liam, who was never in the prompt. The table shows what the tool received and
what the tool result looks like the instant the wrapper hands it back, which is
where FULL and INPUT part ways: FULL re-anonymizes it right there, INPUT leaves
it raw for the next before-model pass to clean. Run with:
uv run examples/strategies/tool_call.py
"""

import asyncio
from typing import Any, Self

from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
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
from piighost.integrations.middleware import ToolCallStrategy
from piighost.integrations.middleware.langchain import PIIAnonymizationMiddleware

# What the tool received and what the wrapper handed back, filled per run so the
# example can print them; a real deployment needs nothing like these.
TOOL_ARG: list[str] = []
TOOL_RESULT_AFTER: list[str] = []


class RecordingMiddleware(PIIAnonymizationMiddleware[PreservesLabeledIdentityOpaque]):
    """Middleware that records the tool result its wrapper hands back.

    Only here to expose the outbound boundary; a real deployment uses the plain
    PIIAnonymizationMiddleware.
    """

    async def awrap_tool_call(self, request: Any, handler: Any) -> Any:
        """Record the tool result right after the wrapper, then return it."""
        response = await super().awrap_tool_call(request, handler)
        if isinstance(response, ToolMessage) and isinstance(response.content, str):
            TOOL_RESULT_AFTER.append(response.content)
        return response


class ScriptedChatModel(GenericFakeChatModel):
    """A deterministic fake model that returns preset messages, no API key.

    It stands in for a real chat model so the example runs offline. bind_tools
    is a no-op because the scripted replies already carry the tool call.
    """

    def bind_tools(self, tools: Any, **kwargs: Any) -> Self:
        """Ignore tool binding, the scripted replies drive the agent."""
        return self


@tool
def lookup_manager(person: str) -> str:
    """Return the manager of a person, naming a second person in the answer."""
    TOOL_ARG.append(person)
    return f"The manager of {person} is Liam."


def _build_pipeline() -> ThreadAnonymizationPipeline[PreservesLabeledIdentityOpaque]:
    """Wire a thread pipeline that knows both people the scenario mentions."""
    ph_factory = LabelCounterPlaceholderFactory()
    return ThreadAnonymizationPipeline(
        ExactMatchDetector({"Emma": "PERSON", "Liam": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(ph_factory),
        InMemoryConversationMemory(),
    )


async def _run_once(strategy: ToolCallStrategy) -> tuple[str, str]:
    """Run the scenario under one strategy, returning the tool arg and its result."""
    TOOL_ARG.clear()
    TOOL_RESULT_AFTER.clear()

    middleware = RecordingMiddleware(_build_pipeline(), tool_strategy=strategy)
    script = iter(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup_manager",
                        "args": {"person": "<<PERSON:1>>"},
                        "id": "c1",
                    }
                ],
            ),
            AIMessage(content="Understood."),
        ]
    )
    model = ScriptedChatModel(messages=script)
    agent = create_agent(model=model, tools=[lookup_manager], middleware=[middleware])

    request = {"messages": [HumanMessage("Who manages Emma?")]}
    config = {"configurable": {"thread_id": "t1"}}
    await agent.ainvoke(request, config=config)

    return TOOL_ARG[0], TOOL_RESULT_AFTER[0]


async def main() -> None:
    """Run every strategy over the same scenario and lay the results side by side."""
    strategies = [
        ToolCallStrategy.FULL,
        ToolCallStrategy.INPUT,
        ToolCallStrategy.OUTPUT,
        ToolCallStrategy.PASSTHROUGH,
    ]

    print(f"{'strategy':12}  {'tool received':15}  tool result right after the wrapper")
    print(f"{'-' * 12}  {'-' * 15}  {'-' * 42}")
    for strategy in strategies:
        tool_arg, result_after = await _run_once(strategy)
        print(f"{strategy.name:12}  {tool_arg!r:15}  {result_after!r}")

    print("\nInbound: FULL and INPUT hand the tool the real value; OUTPUT and")
    print("PASSTHROUGH leave it a placeholder.")
    print("Outbound: FULL and OUTPUT re-anonymize the result on the spot; INPUT and")
    print("PASSTHROUGH leave it raw. INPUT's raw result is cleaned by the next")
    print("before-model pass, so the model still sees placeholders; PASSTHROUGH never")
    print("cleans it, so the tool's second name (Liam) reaches the model in the clear.")


if __name__ == "__main__":
    asyncio.run(main())
