# Not shown: the model, the pipeline and the conversation the page assumes. The
# import the page shows ends its block, with no blank line for the import sorter.
# isort: skip_file
from _offline import offline_langchain

from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import ThreadAnonymizationPipeline

offline_langchain("Hello {0}.", secrets=("Patrick",))
pipeline = ThreadAnonymizationPipeline(ExactMatchDetector({"Patrick": "PERSON"}))
messages = [{"role": "user", "content": "Say hello to Patrick."}]

# isort: split
# --8<-- [start:aliases]
from piighost.integrations.langchain import (
    PIIAnonymizationMiddleware,
)
# --8<-- [end:aliases]


# isort: split
# --8<-- [start:middleware]
middleware = PIIAnonymizationMiddleware(pipeline)
# --8<-- [end:middleware]
# Not shown: the agent the page assumes, around the middleware above.
from langchain.agents import create_agent

agent = create_agent(model="openai:gpt-5.6-terra", middleware=[middleware])
# --8<-- [start:invoke]
await agent.ainvoke(
    {"messages": messages}, config={"configurable": {"thread_id": "default"}}
)
# --8<-- [end:invoke]
