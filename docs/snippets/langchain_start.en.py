# Not shown: the model the page names, replaced by a scripted one.
from _offline import offline_langchain

offline_langchain("{0} lives in {1}.", secrets=("Patrick", "Paris"))

# isort: split
# --8<-- [start:pipeline]
from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.pipeline import ThreadAnonymizationPipeline

detector = ExactMatchDetector({"Patrick": "PERSON", "Paris": "LOCATION"})
linker = ExactEntityLinker()
factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
memory = InMemoryConversationMemory()
pipeline = ThreadAnonymizationPipeline(
    detector,
    linker,
    anonymizer,
    memory,
)
# --8<-- [end:pipeline]


# isort: split
# --8<-- [start:tool]
from langchain.tools import tool


@tool
def lookup_city(person: str) -> str:
    """Return the city where a person lives."""
    directory = {"Patrick": "Paris"}
    return directory.get(person, "unknown")


# --8<-- [end:tool]


# isort: split
# --8<-- [start:agent]
from langchain.agents import create_agent

from piighost.integrations.langchain import (
    PIIAnonymizationMiddleware,
    ToolCallStrategy,
)

agent = create_agent(
    model="openai:gpt-5.6-terra",
    tools=[lookup_city],
    middleware=[
        PIIAnonymizationMiddleware(
            pipeline=pipeline,
            tool_strategy=ToolCallStrategy.FULL,
        )
    ],
)
# --8<-- [end:agent]


# isort: split
# --8<-- [start:run]
import asyncio


async def main() -> None:
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "Where does Patrick live?"}]},
        config={"configurable": {"thread_id": "thread-42"}},
    )
    print(result["messages"][-1].content)


asyncio.run(main())
# --8<-- [end:run]
