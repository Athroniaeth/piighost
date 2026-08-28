# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost[langchain]"]
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
  INPUT        deanonymize the arguments only, leave the result raw
  OUTPUT       re-anonymize the result only, the tool sees placeholders
  PASSTHROUGH  neither, the tool call is untouched

The scenario is the same each time. The model calls lookup_manager with the
person placeholder, and the tool returns a sentence naming a second person,
Liam, who was never in the prompt. The middleware acts only in the tool wrapper,
never on the tool message afterwards, so the wrapper's output is exactly what the
model then sees. The table shows what the tool received, that output, and how
many times the detector ran, and the notes say when to reach for each strategy.
Run with:
uv run examples/strategies/tool_call.py
"""

import asyncio
from typing import Any, Self

from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import AnyDetector, ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import (
    LabelCounterPlaceholderFactory,
    PreservesLabeledIdentityOpaque,
)
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.integrations.langchain import ToolCallStrategy
from piighost.integrations.langchain.middleware import PIIAnonymizationMiddleware
from piighost.models import Detection
from piighost.pipeline import ThreadAnonymizationPipeline

# What the tool received and what the wrapper handed back, filled per run so the
# example can print them; a real deployment needs nothing like these.
TOOL_ARG: list[str] = []
TOOL_RESULT_AFTER: list[str] = []


class _CountingDetector:
    """Wrap a detector to count how many texts it actually scans.

    Only here to expose the cost difference between the strategies; a real
    deployment needs nothing like it.
    """

    def __init__(self, inner: AnyDetector) -> None:
        """Store the wrapped detector and start the call count at zero."""
        self._inner = inner
        self.calls = 0

    async def detect(self, text: str) -> list[Detection]:
        """Count the scan, then delegate to the wrapped detector."""
        self.calls += 1
        return await self._inner.detect(text)


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


def _build_pipeline(
    detector: AnyDetector,
) -> ThreadAnonymizationPipeline[PreservesLabeledIdentityOpaque]:
    """Wire a thread pipeline over the given detector, knowing both people."""
    ph_factory = LabelCounterPlaceholderFactory()
    return ThreadAnonymizationPipeline(
        detector,
        ExactEntityLinker(),
        Anonymizer(ph_factory),
        InMemoryConversationMemory(),
    )


async def _run_once(strategy: ToolCallStrategy) -> tuple[str, str, int]:
    """Run the scenario under one strategy, returning the arg, result, and cost."""
    TOOL_ARG.clear()
    TOOL_RESULT_AFTER.clear()

    detector = _CountingDetector(
        ExactMatchDetector({"Emma": "PERSON", "Liam": "PERSON"})
    )
    middleware = RecordingMiddleware(_build_pipeline(detector), tool_strategy=strategy)
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

    return TOOL_ARG[0], TOOL_RESULT_AFTER[0], detector.calls


async def main() -> None:
    """Run every strategy over the same scenario and lay the results side by side."""
    strategies = [
        ToolCallStrategy.FULL,
        ToolCallStrategy.INPUT,
        ToolCallStrategy.OUTPUT,
        ToolCallStrategy.PASSTHROUGH,
    ]

    print(
        f"{'strategy':12}  {'tool received':15}  {'detector runs':13}  "
        "tool result the model sees"
    )
    print(f"{'-' * 12}  {'-' * 15}  {'-' * 13}  {'-' * 42}")
    for strategy in strategies:
        tool_arg, result_after, calls = await _run_once(strategy)
        print(f"{strategy.name:12}  {tool_arg!r:15}  {calls:<13}  {result_after!r}")

    print("\nWhen to reach for each:")
    print("  FULL         the tool needs the real value and its output must be clean:")
    print("               it gets real PII, the model only ever sees placeholders.")
    print("  INPUT        the tool needs the real value and you pass its output to the")
    print(
        "               model as-is: no output cleaning, so the model may see raw PII."
    )
    print(
        "  OUTPUT       the tool must not see real PII but its output must be cleaned:"
    )
    print("               it works on placeholders, any PII it returns is anonymized.")
    print("  PASSTHROUGH  the tool neither needs nor returns PII: skip all work, the")
    print("               call is left untouched and no extra detector pass is spent.")
    print("\nAnonymizing the tool result (FULL, OUTPUT) costs one extra detector pass;")
    print("INPUT and PASSTHROUGH skip it.")


if __name__ == "__main__":
    asyncio.run(main())
