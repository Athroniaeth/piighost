# Not shown: the model the page names, replaced by a scripted one.
from _offline import offline_langchain

offline_langchain("{1} is a software engineer in {2}.", secrets=("Patrick", "Paris"))

# isort: split
# --8<-- [start:invoke]
from langchain.agents import create_agent
from langchain_core.tools import tool

from piighost.config import load_thread_pipeline
from piighost.integrations.langchain import PIIAnonymizationMiddleware


@tool
def get_info(person: str) -> str:
    """Return information about a person."""
    return f"{person} is a software engineer in Paris."


pipeline = load_thread_pipeline("pipeline.toml")
middleware = PIIAnonymizationMiddleware(pipeline)

agent = create_agent(
    model="openai:gpt-5.6-terra",
    system_prompt="You are a helpful assistant. Treat placeholders as real values.",
    tools=[get_info],
    middleware=[middleware],
)

config = {"configurable": {"thread_id": "conv-1"}}
result = await agent.ainvoke(
    {"messages": [{"role": "user", "content": "Who is Patrick?"}]},
    config,
)
print(result["messages"][-1].content)
# --8<-- [end:invoke]


# isort: split
# --8<-- [start:stream]
from langchain_core.messages import AIMessage

config = {"configurable": {"thread_id": "conv-1"}}


async def model_text():
    async for chunk, _meta in agent.astream(
        {"messages": [{"role": "user", "content": "Who is Patrick?"}]},
        config,
        stream_mode="messages",
    ):
        # The stream carries the tool results too, keep the model's text only.
        if isinstance(chunk, AIMessage) and isinstance(chunk.content, str):
            yield chunk.content


async for restored in middleware.deanonymize_stream(model_text(), "conv-1"):
    print(restored, end="", flush=True)
# --8<-- [end:stream]
