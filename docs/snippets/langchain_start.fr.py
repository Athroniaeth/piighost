# Not shown: the model the page names, replaced by a scripted one.
from _offline import offline_langchain

offline_langchain("{0} habite à {1}.", secrets=("Patrick", "Paris"))

# isort: split
# --8<-- [start:pipeline]
from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import ThreadAnonymizationPipeline

detector = ExactMatchDetector({"Patrick": "PERSON", "Paris": "LOCATION"})
pipeline = ThreadAnonymizationPipeline(detector)
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
        {"messages": [{"role": "user", "content": "Où habite Patrick ?"}]},
        config={"configurable": {"thread_id": "thread-42"}},
    )
    print(result["messages"][-1].content)


asyncio.run(main())
# --8<-- [end:run]
