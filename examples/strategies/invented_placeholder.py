# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost[middleware]"]
#
# [tool.uv.sources]
# piighost = { path = "../..", editable = true }
# ///
"""Handle placeholder tokens the model invents, under each strategy.

A model can echo a token it was given, which deanonymizes cleanly, but it can
also emit one the pipeline never issued, say <<PERSON:9>> when only <<PERSON:1>>
exists, whether by hallucination or prompt injection. After deanonymization
every issued token has been replaced by its value, so any token still matching
the placeholder grammar was invented. The middleware's InventedPlaceholderStrategy
decides what happens then:

  KEEP   leave the invented token in the text
  DROP   remove the invented token from the text
  RAISE  raise InventedPlaceholderError, the fail-closed default

Here the scripted model replies with one real token and one invented token, and
the example runs the reply under each strategy. Run with:
uv run examples/strategies/invented_placeholder.py
"""

import asyncio
from typing import Any, Self

from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage

from piighost.components.anonymizer import Anonymizer
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.exceptions import InventedPlaceholderError
from piighost.pipeline import ThreadAnonymizationPipeline
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.integrations.middleware import (
    InventedPlaceholderStrategy,
    PIIAnonymizationMiddleware,
)

# The reply the fake model returns: it echoes the token for Emma and invents a
# second one the pipeline never issued.
INVENTED_REPLY = "Sure <<PERSON:1>>, I also looped in <<PERSON:9>>."


class ScriptedChatModel(GenericFakeChatModel):
    """A deterministic fake model that returns a preset reply, no API key.

    It stands in for a real chat model so the example runs offline. bind_tools
    is a no-op because the agent uses no tools here.
    """

    def bind_tools(self, tools: Any, **kwargs: Any) -> Self:
        """Ignore tool binding, the scripted reply drives the agent."""
        return self


def _build_agent(strategy: InventedPlaceholderStrategy) -> Any:
    """Attach the middleware under one invented-placeholder strategy to an agent."""
    ph_factory = LabelCounterPlaceholderFactory()
    pipeline = ThreadAnonymizationPipeline(
        ExactMatchDetector({"Emma": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(ph_factory),
        InMemoryConversationMemory(),
    )
    middleware = PIIAnonymizationMiddleware(pipeline, invented_strategy=strategy)
    model = ScriptedChatModel(messages=iter([AIMessage(content=INVENTED_REPLY)]))
    return create_agent(model=model, tools=[], middleware=[middleware])


async def _run_once(strategy: InventedPlaceholderStrategy) -> str:
    """Run the reply under one strategy, returning what the user sees or the error."""
    agent = _build_agent(strategy)
    request = {"messages": [HumanMessage("Tell me about Emma.")]}
    config = {"configurable": {"thread_id": "t1"}}
    try:
        result = await agent.ainvoke(request, config=config)
    except InventedPlaceholderError as error:
        return f"InventedPlaceholderError, tokens={error.tokens}"
    return repr(result["messages"][-1].content)


async def main() -> None:
    """Run the invented reply under every strategy and show the outcomes."""
    print(f"the model reply, before deanonymization: {INVENTED_REPLY!r}")
    print("<<PERSON:1>> is Emma, issued for this thread; <<PERSON:9>> was invented.\n")

    strategies = [
        InventedPlaceholderStrategy.KEEP,
        InventedPlaceholderStrategy.DROP,
        InventedPlaceholderStrategy.RAISE,
    ]
    for strategy in strategies:
        outcome = await _run_once(strategy)
        print(f"  {strategy.name:6} -> {outcome}")


if __name__ == "__main__":
    asyncio.run(main())
