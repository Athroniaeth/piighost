# Not shown: the model the page names, replaced by a scripted one, and the
# pipeline of pydantic_ai_pipeline.py, with a detector that needs no model.
from _offline import offline_pydantic_ai

from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import ThreadAnonymizationPipeline

offline_pydantic_ai("I have no address for {0}.", secrets=("Patrick",))
pipeline = ThreadAnonymizationPipeline(ExactMatchDetector({"Patrick": "PERSON"}))

# isort: split
# --8<-- [start:agent]
from pydantic_ai import Agent

from piighost.integrations.pydantic_ai import pii_hooks

hooks = pii_hooks(pipeline, "thread-42")
agent = Agent("openai:gpt-5.6-terra", capabilities=[hooks])
# --8<-- [end:agent]


# isort: split
# --8<-- [start:run]
import asyncio


async def main() -> None:
    result = await agent.run("Where does Patrick live?")
    print(result.output)


asyncio.run(main())
# --8<-- [end:run]


# isort: split
# --8<-- [start:invented]
from piighost.integrations.langchain import InventedPlaceholderStrategy

hooks = pii_hooks(
    pipeline,
    "thread-42",
    invented_strategy=InventedPlaceholderStrategy.DROP,
)
# --8<-- [end:invented]


# isort: split
# --8<-- [start:tools]
from piighost.integrations.langchain import ToolCallStrategy

hooks = pii_hooks(pipeline, "thread-42", tool_strategy=ToolCallStrategy.FULL)
# --8<-- [end:tools]


# isort: split
# --8<-- [start:assistant]
from piighost.integrations.langchain import EntityCreateByAssistantStrategy

hooks = pii_hooks(
    pipeline,
    "thread-42",
    assistant_strategy=EntityCreateByAssistantStrategy.ANONYMIZE,
)
# --8<-- [end:assistant]
