# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost[pydantic-ai]", "python-dotenv>=1.0"]
#
# [tool.uv.sources]
# piighost = { path = "../..", editable = true }
# ///
"""Run a Pydantic AI agent behind the PII de-identification capability.

pii_hooks returns a capability that sits around the model boundary of a Pydantic
AI agent. It anonymizes every user and assistant text before the model sees it,
so the model only ever works on placeholders, even across a multi-turn history,
and deanonymizes the model's reply for the user. The thread id given here is a
fixed string, but it can also be a callable over the run context.

The agent runs against openai:gpt-5.5, so set an OPENAI_API_KEY in the
environment (copy .env.example to .env). Run with:
uv run examples/pydantic_ai/hooks.py
"""

import asyncio

from dotenv import load_dotenv
from pydantic_ai import Agent

from piighost.components.detector import ExactMatchDetector
from piighost.integrations.pydantic_ai import pii_hooks
from piighost.pipeline import ThreadAnonymizationPipeline


async def main() -> None:
    """Run a two-turn conversation with the model working only on placeholders."""
    load_dotenv()
    detector = ExactMatchDetector({"Emma": "PERSON"})
    pipeline = ThreadAnonymizationPipeline(detector)
    hooks = pii_hooks(pipeline, "demo-thread")
    agent = Agent("openai:gpt-5.5", capabilities=[hooks])

    first = await agent.run("Hi, I am Emma. Book me a slot.")
    second = await agent.run("Remind me my name?", message_history=first.all_messages())

    print(f"turn 1: {first.output!r}")
    print(f"turn 2: {second.output!r}")


if __name__ == "__main__":
    asyncio.run(main())
