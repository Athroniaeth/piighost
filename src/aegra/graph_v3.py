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

graph = create_agent(
    model="openai:gpt-4o",
    tools=[send_email, get_weather],
    middleware=[pii],
)
