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

The scenario is the same each time: the assistant says 'It was Napoleon.', then
the user asks 'What did Napoleon do?'. Both turns run through the middleware. The
table shows what the model sees for each message and how many times the detector
ran, which is where ANONYMIZE and IGNORE part ways. Run with:
uv run examples/strategies/assistant_entity.py
"""

import asyncio
import logging
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from piighost.components.anonymizer import Anonymizer
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.components.detector import AnyDetector, ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.models import Detection
from piighost.pipeline import ThreadAnonymizationPipeline
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.integrations.middleware import AssistantEntityStrategy
from piighost.integrations.middleware.langchain import PIIAnonymizationMiddleware

# The demo calls abefore_model directly, outside a LangGraph run, so no thread id
# is in scope. require_thread_id=False routes every turn to the shared default
# thread; silence the one-time warning that points this out.
logging.getLogger(PIIAnonymizationMiddleware.__module__).setLevel(logging.ERROR)


class _CountingDetector:
    """Wrap a detector to count how many messages it actually scans.

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


def _content(message: BaseMessage) -> str:
    """Return a message's text content, a plain string in this example."""
    content = message.content
    return content if isinstance(content, str) else str(content)


def _middleware(strategy: AssistantEntityStrategy, detector: AnyDetector) -> Any:
    """Build the middleware over a fresh pipeline under one strategy."""
    pipeline = ThreadAnonymizationPipeline(
        detector,
        ExactEntityLinker(),
        Anonymizer(LabelCounterPlaceholderFactory()),
        InMemoryConversationMemory(),
    )
    return PIIAnonymizationMiddleware(
        pipeline, assistant_strategy=strategy, require_thread_id=False
    )


async def _run_once(strategy: AssistantEntityStrategy) -> tuple[str, str, int]:
    """Run the assistant then user turn, returning both texts and detector calls."""
    detector = _CountingDetector(ExactMatchDetector({"Napoleon": "PERSON"}))
    middleware = _middleware(strategy, detector)

    assistant = {"messages": [AIMessage("It was Napoleon.")]}
    await middleware.abefore_model(assistant, None)
    assistant_seen = _content(assistant["messages"][0])

    user = {"messages": [HumanMessage("What did Napoleon do?")]}
    await middleware.abefore_model(user, None)
    user_seen = _content(user["messages"][0])

    return assistant_seen, user_seen, detector.calls


async def main() -> None:
    """Run every strategy over the scenario and lay the results side by side."""
    print(
        "assistant says: 'It was Napoleon.'  then user asks: 'What did Napoleon do?'\n"
    )
    print(
        f"{'strategy':10}  {'assistant msg -> model':24}  {'user msg -> model':26}  detector runs"
    )
    print(f"{'-' * 10}  {'-' * 24}  {'-' * 26}  {'-' * 13}")

    strategies = [
        AssistantEntityStrategy.PRESERVE,
        AssistantEntityStrategy.ANONYMIZE,
        AssistantEntityStrategy.IGNORE,
    ]
    for strategy in strategies:
        assistant_seen, user_seen, calls = await _run_once(strategy)
        print(f"{strategy.name:10}  {assistant_seen!r:24}  {user_seen!r:26}  {calls}")

    print("\nPRESERVE keeps the assistant's entity in clear on both turns.")
    print("ANONYMIZE tokenizes it everywhere, analyzing the assistant message too.")
    print("IGNORE never analyzes the assistant message (one fewer detector run), so")
    print("the entity is anonymized only once the user re-introduces it.")


if __name__ == "__main__":
    asyncio.run(main())
