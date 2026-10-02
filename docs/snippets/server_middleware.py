# Not shown: the model the page names, replaced by a scripted one.
from _offline import offline_langchain

offline_langchain("", secrets=())

# isort: split
# --8<-- [start:example]
from langchain.agents import create_agent

from piighost.integrations.client import PIIGhostClient
from piighost.integrations.langchain import PIIAnonymizationMiddleware

client = PIIGhostClient("http://localhost:8000")

agent = create_agent(
    model="openai:gpt-5.6-terra",
    middleware=[PIIAnonymizationMiddleware(pipeline=client)],
)
# --8<-- [end:example]
