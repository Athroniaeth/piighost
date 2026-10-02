# Not shown: the model the page names, replaced by a scripted one, and the
# pipeline of langchain_pipeline.py, with a detector that needs no model.
from _offline import offline_langchain

from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import ThreadAnonymizationPipeline

offline_langchain("{0} lives in {1}.", secrets=("Patrick", "Paris"))
pipeline = ThreadAnonymizationPipeline(
    ExactMatchDetector({"Patrick": "PERSON", "Paris": "LOCATION"})
)

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
# --8<-- [start:system_prompt]
SYSTEM_PROMPT = """\
You are a helpful assistant. Some inputs contain placeholders like <<PERSON:1>> \
that stand in for real values withheld for privacy.

Treat each placeholder as if it were the real value. Never comment on its \
format, never say it is a token, and pass it to tools unchanged as an argument. \
If the user asks about the content of a placeholder, say the data is withheld \
and you cannot reveal it.
"""
# --8<-- [end:system_prompt]


# isort: split
# --8<-- [start:agent]
from langchain.agents import create_agent

from piighost.integrations.langchain import (
    PIIAnonymizationMiddleware,
    ToolCallStrategy,
)

agent = create_agent(
    model="openai:gpt-5.6-terra",
    system_prompt=SYSTEM_PROMPT,
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
