"""Agent graph wired with PII anonymization middleware for end-to-end testing."""

from __future__ import annotations

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.tools import tool
from loguru import logger

from aegra.middleware import PIIAnonymizationMiddleware

load_dotenv()


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email to a given address.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Email body text.

    Returns:
        Confirmation string.
    """
    logger.info("\n[EMAIL SENT] To: {} | Subject: {}\n{}\n", to, subject, body)
    return f"Email successfully sent to {to}."


@tool
def get_weather(country_or_city: str) -> str:
    """Get the current weather for a given country or city.

    Args:
        country_or_city: Name of the location to query.

    Returns:
        A weather summary string.
    """
    return f"The weather in {country_or_city} is 22°C and sunny."


pii = PIIAnonymizationMiddleware(threshold=0.5)

_SYSTEM_PROMPT = """\
You are a helpful assistant. Some inputs may contain anonymized tokens \
(e.g. <PERSON:a1b2c3>, <LOCATION:x9y8z7>, <EMAIL_ADDRESS:d4e5f6>) that replace \
real values for privacy reasons.

Rules:
1. Treat every token as if it were the real value — never comment on its format, \
never say it is a token, never ask the user to reveal it.
2. Tokens can be passed directly to tools — use them as-is as input arguments \
(e.g. get_weather(<LOCATION:a1b2c3>)). This preserves the user's privacy while \
still allowing tools to operate.
3. If a tool returns no result because a token is unresolvable, give a short, \
natural explanation in one sentence — no technical jargon.
4. Never expose internal reasoning about anonymization to the user.
5. If the user asks for a specific detail about a token (e.g. "what is the first \
letter?"), reply briefly: "I cannot answer that question as the data has been \
anonymized to protect your personal information."
"""

graph = create_agent(
    model="openai:gpt-4o",
    system_prompt=_SYSTEM_PROMPT,
    tools=[send_email, get_weather],
    middleware=[pii],
)
