"""Agent graph wired with PII anonymization middleware for end-to-end testing."""
from typing import Any, Callable, Awaitable

from dotenv import load_dotenv
from langchain.agents import create_agent, AgentState
from langchain.agents.middleware import hook_config, AgentMiddleware, ModelRequest, ExtendedModelResponse
from langchain.agents.middleware.types import StateT, ModelResponse, ResponseT
from langchain_core.messages import AIMessage, AnyMessage
from langchain_core.tools import tool
from langgraph.runtime import Runtime
from langgraph.typing import ContextT
from loguru import logger
from langfuse import get_client
from langfuse.langchain import CallbackHandler

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

class Anonymizer:
    def anonymize_state(self, state: AgentState) -> AgentState:
        new_messages = []
        for message in state["messages"]:
            message.content = message.content.replace("Pierre", "{name}")
            message.content = message.content.replace("Lyon", "{city}")
            new_messages.append(message)
        return state

    def deanonymize_state(self, state: AgentState) -> AgentState:
        for message in state["messages"]:
            if "{name}" in message.content:
                message.content = message.content.replace("{name}", "Pierre")
            if "{city}" in message.content:
                message.content = message.content.replace("{city}", "Lyon")
        return state
    def deanonymize_messages(self, messages: list[AnyMessage]) -> list[AnyMessage]:
        for message in messages:
            if "{name}" in message.content:
                message.content = message.content.replace("{name}", "Pierre")
            if "{city}" in message.content:
                message.content = message.content.replace("{city}", "Lyon")
        return messages

class CustomMiddleware(AgentMiddleware):
    def __init__(self):
        super().__init__()
        self.anonymizer = Anonymizer()

    def before_model(self, state: AgentState, runtime: Runtime) -> AgentState | None:
        # if len(state["messages"]) >= self.max_messages:
        #     response: AgentState = {
        #         "messages": [AIMessage("Conversation limit reached.")],
        #         "jump_to": "end"
        #     }
        #     return response

        # Ne cache rien sur l'interface et rechargement
        print(f"Messages: {[m.content for m in state['messages']]}")
        state = self.anonymizer.anonymize_state(state)
        print(f"Messages after deanonymization: {[m.content for m in state['messages']]}")

        return None

    def after_model(self, state: AgentState, runtime: Runtime) -> AgentState | None:

        # Ne cache rien sur l'interface et rechargement
        print(f"Messages (anon): {[m.content for m in state['messages']]}")
        state = self.anonymizer.deanonymize_state(state)
        print(f"Messages after deanonymization: {[m.content for m in state['messages']]}")
        return None

    def after_agent(self, state: StateT, runtime: Runtime[ContextT]) -> AgentState | None:
        # This runs after the entire agent execution, just before returning the final response.
        # You can use it to modify the final output or perform any cleanup actions.
        print(f"Final state before returning response: {[m.content for m in state['messages']]}")
        return None


    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT] | AIMessage | ExtendedModelResponse[ResponseT]:
        # Cache uniquement la réponse du modèle sur l'interface et au rechargement du thread
        print(f"Request: {request.messages}")
        print(f"Model request: {[m.content for m in request.messages]}")
        response = await handler(request)
        ai_msg = response.result[0]
        ai_msg = self.anonymizer.deanonymize_messages([ai_msg])[0]
        request.messages = self.anonymizer.deanonymize_messages(request.messages)
        return ModelResponse(
            result=[AIMessage(content=f"{ai_msg.content}")],
            structured_response=response.structured_response,
        )

system_prompt = """\
You are a helpful assistant. Some inputs may contain anonymized placeholders that replace real values for privacy reasons.

Rules:
1. Treat every placeholder as if it were the real value, never comment on its format, never say it is a token, never ask the user to reveal it.
2. Placeholders can be passed directly to tools — use them as-is as input arguments. This preserves the user's privacy while \
still allowing tools to operate.
3. If the user asks for a specific detail about a token (e.g. "what is the first letter?"), reply briefly: "I cannot answer that question as the data has been anonymized to protect your personal information." \
Another example is if the user asks "Dans quel pays ce trouve la ville de {city} ?", you can answer "Je suis désolé, mais je ne peux pas répondre à cette question car les données ont été anonymisées pour protéger vos informations personnelles."
"""

# Initialize Langfuse client
langfuse = get_client()

# Initialize Langfuse CallbackHandler for Langchain (tracing)
langfuse_handler = CallbackHandler()

middleware = CustomMiddleware()

graph = create_agent(
    model="openai:gpt-5-nano",
    system_prompt=system_prompt,
    tools=[send_email, get_weather],
    middleware=[middleware],
)
