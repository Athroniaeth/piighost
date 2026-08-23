# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost[langchain]", "langchain-openai>=0.3", "python-dotenv>=1.0"]
#
# [tool.uv.sources]
# piighost = { path = "../..", editable = true }
# ///
"""Run a real LangGraph agent whose model only ever sees PII tokens.

This mirrors the minimal middleware snippet, end to end against a live model. A
fake exact-match detector feeds a ThreadAnonymizationPipeline wrapped in
PIIAnonymizationMiddleware. The user asks to email Patrick Dupont; the model
plans the send_mail call over <<PERSON:1>> and <<EMAIL:1>>, the tool receives the
real address under the default FULL tool strategy, and the reply is restored
before it is shown. The tool prints what it actually received, so you can see it
got the real values while the model only ever handled tokens.

Set OPENAI_API_KEY in examples/.env, loaded below. Run with:
uv run examples/langchain/send_mail.py
"""

import asyncio
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from piighost.components.detector import ExactMatchDetector
from piighost.integrations.langchain import PIIAnonymizationMiddleware
from piighost.pipeline import ThreadAnonymizationPipeline

SYSTEM_PROMPT = (
    "Some inputs contain placeholders like <<PERSON:1>> that stand in for real "
    "values withheld for privacy. Treat each placeholder as the real value, never "
    "comment on its format, and pass it to tools unchanged."
)


@tool
def send_mail(to: str, body: str) -> str:
    """Send an email to `to` with the given body."""
    print(f"[tool] send_mail received to={to!r}")
    return f"Email sent to {to}."


async def main() -> None:
    """Email a recipient the model only ever knows as a token."""
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    labels = {"Patrick Dupont": "PERSON", "patrick@acme.com": "EMAIL"}
    detector = ExactMatchDetector(labels)
    pipeline = ThreadAnonymizationPipeline(detector)
    middleware = PIIAnonymizationMiddleware(pipeline)
    # gpt-5.6-terra is a reasoning model; chat/completions rejects function
    # tools unless reasoning_effort is none, so set it before binding the tool.
    model = init_chat_model("openai:gpt-5.6-terra", reasoning_effort="none")
    agent = create_agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[send_mail],
        middleware=[middleware],
    )
    config = {"configurable": {"thread_id": "demo-thread"}}

    prompt = "Use the send_mail tool to send a welcome note to Patrick Dupont at patrick@acme.com."
    request = {"messages": [HumanMessage(prompt)]}
    result = await agent.ainvoke(request, config=config)
    print(f"user sees: {result['messages'][-1].content!r}")


if __name__ == "__main__":
    asyncio.run(main())
