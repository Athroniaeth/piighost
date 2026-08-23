# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost[langchain]", "langchain-openai>=0.3", "python-dotenv>=1.0"]
#
# [tool.uv.sources]
# piighost = { path = "../..", editable = true }
# ///
"""Run a LangChain agent behind the PII anonymization middleware.

PIIAnonymizationMiddleware sits around the model boundary of a LangGraph agent.
It anonymizes every user and assistant message before the model sees it, so the
model only ever works on placeholders, even across a multi-turn history, and
deanonymizes the reply for the user. The thread id is read from the LangGraph
config, under configurable.

The agent runs against openai:gpt-5.5, so set an OPENAI_API_KEY in the
environment (copy .env.example to .env). For a tool-calling agent, see tools.py
beside this file. Run with:
uv run examples/langchain/base.py
"""

import asyncio
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from piighost.components.detector import ExactMatchDetector
from piighost.integrations.langchain import PIIAnonymizationMiddleware
from piighost.pipeline import ThreadAnonymizationPipeline


async def main() -> None:
    """Ask for the first letter of a name the model only ever sees as a token.

    The model receives <<PERSON:1>>, not Emma, so it cannot tell that the name
    starts with E. Its own answer to the second turn shows the anonymization
    held, without any extra instrumentation.
    """
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    detector = ExactMatchDetector({"Emma": "PERSON"})
    pipeline = ThreadAnonymizationPipeline(detector)
    middleware = PIIAnonymizationMiddleware(pipeline)
    agent = create_agent(model="openai:gpt-5.5", middleware=[middleware])
    config = {"configurable": {"thread_id": "demo-thread"}}

    first = await agent.ainvoke(
        {"messages": [HumanMessage("Hi, I am Emma.")]}, config=config
    )
    history = first["messages"]
    second = await agent.ainvoke(
        {
            "messages": [
                *history,
                HumanMessage("What is the first letter of my first name?"),
            ]
        },
        config=config,
    )

    print(f"turn 1: {first['messages'][-1].content!r}")
    print(f"turn 2: {second['messages'][-1].content!r}")


if __name__ == "__main__":
    asyncio.run(main())
