# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost[pydantic-ai]", "python-dotenv>=1.0"]
#
# [tool.uv.sources]
# piighost = { path = "../..", editable = true }
# ///
"""Run a Pydantic AI agent whose tool receives the real value, not the token.

pii_hooks de-identifies around the model and, under the default FULL tool
strategy, around the tool boundary too. The model plans the call on <<PERSON:1>>,
but the argument is deanonymized before send_email runs, so the tool works on the
real recipient, and the tool's result is re-anonymized before it returns to the
model. The tool prints what it actually received, so you can see it got Emma
while the model only ever handled the token.

The agent runs against openai:gpt-5.6-terra, so set an OPENAI_API_KEY in the
environment (copy .env.example to .env). Run with:
uv run examples/pydantic_ai/tools.py
"""

import asyncio

from dotenv import load_dotenv
from pydantic_ai import Agent

from piighost.components.detector import ExactMatchDetector
from piighost.integrations.pydantic_ai import pii_hooks
from piighost.pipeline import ThreadAnonymizationPipeline


def send_email(to: str, body: str) -> str:
    """Send an email to a person and confirm it, working on the real recipient."""
    print(f"[tool] send_email received to={to!r}")
    return f"Email delivered to {to}."


async def main() -> None:
    """Email someone the agent knows only as a token, showing the tool got the value."""
    load_dotenv()
    detector = ExactMatchDetector({"Emma": "PERSON"})
    pipeline = ThreadAnonymizationPipeline(detector)
    hooks = pii_hooks(pipeline, "demo-thread")
    agent = Agent(
        "openai:gpt-5.6-terra",
        tools=[send_email],
        capabilities=[hooks],
    )

    result = await agent.run("Email Emma to confirm her booking.")
    print(f"user sees: {result.output!r}")


if __name__ == "__main__":
    asyncio.run(main())
