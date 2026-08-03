# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost[middleware]"]
#
# [tool.uv.sources]
# piighost = { path = "../..", editable = true }
# ///
"""Preserve entities the assistant introduces, under each strategy.

A value the model itself names, say a public figure like Napoleon, is not user
PII. Anonymizing it would strip the model of its world knowledge of that entity.
The provenance rule keys on a value's first occurrence in the thread: introduced
by the assistant, it is left in clear; introduced by the user, it stays
anonymized. AssistantEntityStrategy chooses the behavior:

  PRESERVE   leave assistant-introduced values in clear (default)
  ANONYMIZE  anonymize them like user PII
  IGNORE     do not analyze assistant messages at all, saving the detector

Here the assistant first names Napoleon, then the user asks about him. The
example anonymizes that user turn under each strategy and prints what the model
would receive. Run with:
uv run examples/strategies/assistant_entity.py
"""

import asyncio

from langchain_core.messages import AIMessage, HumanMessage

from piighost.components.anonymizer import Anonymizer
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.pipeline import ThreadAnonymizationPipeline
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.integrations.middleware import (
    AssistantEntityStrategy,
    PIIAnonymizationMiddleware,
)
import piighost.integrations.middleware.langchain as middleware_module


def _middleware(strategy: AssistantEntityStrategy) -> PIIAnonymizationMiddleware:
    """Build the middleware over a fresh pipeline under one strategy."""
    pipeline = ThreadAnonymizationPipeline(
        ExactMatchDetector({"Napoleon": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(LabelCounterPlaceholderFactory()),
        InMemoryConversationMemory(),
    )
    return PIIAnonymizationMiddleware(pipeline, assistant_strategy=strategy)


async def _run_once(strategy: AssistantEntityStrategy) -> str:
    """Let the assistant name Napoleon, then anonymize the user's follow-up."""
    middleware_module.get_config = lambda: {"configurable": {"thread_id": "t1"}}
    middleware = _middleware(strategy)

    await middleware.abefore_model({"messages": [AIMessage("It was Napoleon.")]}, None)
    state = {"messages": [HumanMessage("What did Napoleon do?")]}
    await middleware.abefore_model(state, None)
    return state["messages"][0].content


async def main() -> None:
    """Anonymize the user's Napoleon question under every strategy."""
    print("assistant introduced: 'It was Napoleon.'")
    print("user then asks:        'What did Napoleon do?'\n")

    strategies = [
        AssistantEntityStrategy.PRESERVE,
        AssistantEntityStrategy.ANONYMIZE,
        AssistantEntityStrategy.IGNORE,
    ]
    for strategy in strategies:
        seen = await _run_once(strategy)
        print(f"  {strategy.name:9} -> model sees: {seen!r}")


if __name__ == "__main__":
    asyncio.run(main())
