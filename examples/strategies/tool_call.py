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
Liam, who was never in the prompt. That second name is the tell: only
PASSTHROUGH lets it reach the model in the clear. Run with:
uv run examples/strategies/tool_call.py
"""

import asyncio
from typing import Any, Self

from langchain.agents import create_agent
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatResult
from langchain_core.tools import tool

from piighost.components.anonymizer import Anonymizer
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.pipeline import ThreadAnonymizationPipeline
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.integrations.middleware import (
    PIIAnonymizationMiddleware,
    ToolCallStrategy,
)

# What the tool received and what the model saw as the tool result, filled per
# run so the example can print them; a real deployment needs nothing like these.
TOOL_ARG: list[str] = []
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
            [message.content for message in messages if message.content]
        )
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


@tool
def lookup_manager(person: str) -> str:
    """Return the manager of a person, naming a second person in the answer."""
    TOOL_ARG.append(person)
    return f"The manager of {person} is Liam."


def _build_pipeline() -> ThreadAnonymizationPipeline:
    """Wire a thread pipeline that knows both people the scenario mentions."""
    ph_factory = LabelCounterPlaceholderFactory()
    return ThreadAnonymizationPipeline(
        ExactMatchDetector({"Emma": "PERSON", "Liam": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(ph_factory),
        InMemoryConversationMemory(),
    )


async def _run_once(strategy: ToolCallStrategy) -> tuple[str, str]:
    """Run the scenario under one strategy, returning what the tool and model saw."""
    TOOL_ARG.clear()
    MODEL_INPUTS.clear()

    middleware = PIIAnonymizationMiddleware(_build_pipeline(), tool_strategy=strategy)
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

    tool_result_seen = MODEL_INPUTS[1][-1]
    return TOOL_ARG[0], tool_result_seen


async def main() -> None:
    """Run every strategy over the same scenario and lay the results side by side."""
    strategies = [
        ToolCallStrategy.FULL,
        ToolCallStrategy.INPUT,
        ToolCallStrategy.OUTPUT,
        ToolCallStrategy.PASSTHROUGH,
    ]

    print(f"{'strategy':12}  {'tool received':18}  model saw the tool result as")
    print(f"{'-' * 12}  {'-' * 18}  {'-' * 40}")
    for strategy in strategies:
        tool_arg, tool_result_seen = await _run_once(strategy)
        print(f"{strategy.name:12}  {tool_arg!r:18}  {tool_result_seen!r}")

    print("\nOnly PASSTHROUGH lets the tool's second name (Liam) reach the model")
    print("in the clear; FULL and INPUT also hand the tool the real value.")


if __name__ == "__main__":
    asyncio.run(main())
