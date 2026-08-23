# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost[langchain]", "langchain-openai>=0.3", "python-dotenv>=1.0"]
#
# [tool.uv.sources]
# piighost = { path = "../..", editable = true }
# ///
"""Run a LangChain agent whose tool receives the real value, not the token.

PIIAnonymizationMiddleware de-identifies around the model and, under its default
FULL tool strategy, around the tool boundary too. The model plans the call on
<<PERSON:1>>, but the argument is deanonymized before send_email runs, so the
tool works on the real recipient, and the tool's result is re-anonymized before
it returns to the model. The tool prints what it actually received, so you can
see it got Emma while the model only ever handled the token.

The agent runs against openai:gpt-5.5, so set an OPENAI_API_KEY in the
environment (copy .env.example to .env). Run with:
uv run examples/langchain/tools.py
"""

import asyncio

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from piighost.components.detector import ExactMatchDetector
from piighost.integrations.langchain import PIIAnonymizationMiddleware
from piighost.pipeline import ThreadAnonymizationPipeline


@tool
def send_email(to: str, body: str) -> str:
    """Send an email to a person and confirm it."""
    print(f"[tool] send_email received to={to!r}")
    return f"Email delivered to {to}."


async def main() -> None:
    """Email someone the agent knows only as a token, showing the tool got the value."""
    load_dotenv()
    detector = ExactMatchDetector({"Emma": "PERSON"})
    pipeline = ThreadAnonymizationPipeline(detector)
    middleware = PIIAnonymizationMiddleware(pipeline)
    agent = create_agent(
        model="openai:gpt-5.5",
        tools=[send_email],
        middleware=[middleware],
    )
    config = {"configurable": {"thread_id": "demo-thread"}}

    request = {"messages": [HumanMessage("Email Emma to confirm her booking.")]}
    result = await agent.ainvoke(request, config=config)
    print(f"user sees: {result['messages'][-1].content!r}")


if __name__ == "__main__":
    asyncio.run(main())
