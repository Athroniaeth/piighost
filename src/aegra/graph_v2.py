from __future__ import annotations

import hashlib
from typing import Any, Awaitable, Callable

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    ModelRequest,
    ModelResponse,
)
from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolCall
from langchain_core.tools import tool
from langgraph.runtime import Runtime
from langgraph.types import Command
from loguru import logger
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
load_dotenv()


def _build_analyzer(language: str, spacy_model: str) -> AnalyzerEngine:
    """Build a Presidio AnalyzerEngine with the given spaCy model."""
    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": language, "model_name": spacy_model}],
        }
    )
    return AnalyzerEngine(nlp_engine=provider.create_engine())


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class PIIAnonymizationMiddleware(AgentMiddleware):
    """Middleware that anonymizes PII for the LLM and deanonymizes for the user.

    Maintains a bidirectional mapping so that:
      - Every message sent to the model has PII replaced by deterministic
        placeholder tokens  (e.g.  ``<PERSON:a1b2c3d4>``).
      - Every message returned to the user has those tokens replaced back
        with the original values.
      - Tool call arguments are anonymized before execution; tool results
        are anonymized before being fed back to the model.

    The mapping is **deterministic per value**: the same input always
    produces the same token, so the LLM can reason about identity
    ("same person mentioned twice") without ever seeing real data.

    Parameters
    ----------
    analyzed_fields : list[str]
        Presidio entity types to detect.
        Common values: PERSON, EMAIL_ADDRESS, PHONE_NUMBER, LOCATION, …
    language : str
        Language code for analysis (default ``"fr"``).
    spacy_model : str
        spaCy model name matching *language* (default ``"fr_core_news_lg"``).
    extra_patterns : list[tuple[str, str, str]] | None
        Additional ``(entity_type, regex_pattern, description)`` tuples
        for custom detectors (e.g. SSN, IBAN).
    """

    def __init__(
        self,
        analyzed_fields: list[str] | None = None,
        language: str = "fr",
        spacy_model: str = "fr_core_news_lg",
        extra_patterns: list[tuple[str, str, str]] | None = None,
    ) -> None:
        super().__init__()
        self.language = language
        self.analyzed_fields = analyzed_fields or [
            "PERSON",
            "PHONE_NUMBER",
            "EMAIL_ADDRESS",
            "ORGANIZATION",
            "LOCATION",
        ]

        # Presidio analyzer
        self._analyzer = _build_analyzer(language, spacy_model)

        # Register extra regex-based recognisers
        if extra_patterns:
            from presidio_analyzer import Pattern, PatternRecognizer

            for entity_type, regex, description in extra_patterns:
                recognizer = PatternRecognizer(
                    supported_entity=entity_type,
                    patterns=[Pattern(name=entity_type, regex=regex, score=0.9)],
                    supported_language=self.language,
                )
                self._analyzer.registry.add_recognizer(recognizer)
                if entity_type not in self.analyzed_fields:
                    self.analyzed_fields.append(entity_type)

        # Bidirectional mapping: token ↔ original
        self._to_token: dict[str, str] = {}  # original  → token
        self._to_original: dict[str, str] = {}  # token → original

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def mapping(self) -> dict[str, str]:
        """Return a *copy* of the current token → original mapping."""
        return dict(self._to_original)

    def deanonymize(self, text: str) -> str:
        """Replace all tokens in *text* with their original values."""
        for token, original in self._to_original.items():
            text = text.replace(token, original)
        return text

    def anonymize(self, text: str) -> str:
        """Detect PII in *text* and replace with deterministic tokens."""
        # 1. Replace any already-known original values using the existing mapping
        for original, token in self._to_token.items():
            text = text.replace(original, token)

        # 2. Run Presidio to catch any new PII not yet in the mapping
        results = self._analyzer.analyze(
            text=text,
            language=self.language,
            entities=self.analyzed_fields,
        )

        # Sort by start position descending so replacements don't shift indices
        results = sorted(results, key=lambda r: r.start, reverse=True)

        for result in results:
            original = text[result.start : result.end]
            token = self._get_or_create_token(original, result.entity_type)
            text = text[: result.start] + token + text[result.end :]

        return text

    # ------------------------------------------------------------------
    # Middleware hooks
    # ------------------------------------------------------------------

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Anonymize inbound messages, call the model, deanonymize nothing
        (the model's response stays anonymized in state so it can reference
        its own tokens).  Deanonymization happens in ``after_agent``."""

        # 1. Anonymize every message the model will see
        anonymized_messages = [self._anonymize_message(m) for m in request.messages]

        # 2. Anonymize system message if present
        anonymized_system = request.system_message
        if request.system_message and request.system_message.content:
            anonymized_system = SystemMessage(
                content=self.anonymize(
                    request.system_message.content
                    if isinstance(request.system_message.content, str)
                    else str(request.system_message.content)
                )
            )

        # 3. Call the model with anonymized input
        response = handler(
            request.override(
                messages=anonymized_messages,
                system_message=anonymized_system,
            )
        )

        return response

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Async version of wrap_model_call."""
        anonymized_messages = [self._anonymize_message(m) for m in request.messages]

        anonymized_system = request.system_message
        if request.system_message and request.system_message.content:
            anonymized_system = SystemMessage(
                content=self.anonymize(
                    request.system_message.content
                    if isinstance(request.system_message.content, str)
                    else str(request.system_message.content)
                )
            )

        response = await handler(
            request.override(
                messages=anonymized_messages,
                system_message=anonymized_system,
            )
        )

        return response

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """Deanonymize tool arguments before execution (so the tool works
        with real data), then anonymize the result before it goes back to
        the model."""

        # 1. Deanonymize tool call arguments
        deanonymized_args = {
            k: self.deanonymize(v) if isinstance(v, str) else v
            for k, v in request.tool_call["args"].items()
        }
        deanonymized_tool_call: ToolCall = {
            **request.tool_call,
            "args": deanonymized_args,
        }

        # Build a new request with deanonymized args
        new_request = ToolCallRequest(
            tool_call=deanonymized_tool_call,
            tool=request.tool,
            state=request.state,
            runtime=request.runtime,
        )

        # 2. Execute the tool with real values
        result = handler(new_request)

        # 3. Anonymize the result before it goes back to the model
        if isinstance(result, ToolMessage):
            anonymized_content = self.anonymize(
                result.content
                if isinstance(result.content, str)
                else str(result.content)
            )
            return ToolMessage(
                content=anonymized_content,
                tool_call_id=result.tool_call_id,
                name=result.name,
            )

        return result

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """Async version of wrap_tool_call."""
        deanonymized_args = {
            k: self.deanonymize(v) if isinstance(v, str) else v
            for k, v in request.tool_call["args"].items()
        }
        deanonymized_tool_call: ToolCall = {
            **request.tool_call,
            "args": deanonymized_args,
        }

        new_request = ToolCallRequest(
            tool_call=deanonymized_tool_call,
            tool=request.tool,
            state=request.state,
            runtime=request.runtime,
        )

        result = await handler(new_request)

        if isinstance(result, ToolMessage):
            anonymized_content = self.anonymize(
                result.content
                if isinstance(result.content, str)
                else str(result.content)
            )
            return ToolMessage(
                content=anonymized_content,
                tool_call_id=result.tool_call_id,
                name=result.name,
            )

        return result

    def after_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        """Deanonymize the final assistant message so the user sees real values."""
        if not state.get("messages"):
            return None

        last = state["messages"][-1]
        if not isinstance(last, AIMessage):
            return None

        original_content = (
            self.deanonymize(last.content)
            if isinstance(last.content, str)
            else last.content
        )

        if original_content == last.content:
            return None

        return {
            "messages": [
                AIMessage(
                    content=original_content,
                    tool_calls=last.tool_calls if hasattr(last, "tool_calls") else [],
                    id=last.id,
                )
            ]
        }

    async def aafter_agent(
        self, state: AgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        """Async version of after_agent."""
        return self.after_agent(state, runtime)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_token(self, original: str, entity_type: str) -> str:
        """Return deterministic token for *original*, creating it if needed."""
        if original in self._to_token:
            return self._to_token[original]

        h = _short_hash(original)
        token = f"<{entity_type}:{h}>"

        self._to_token[original] = token
        self._to_original[token] = original
        return token

    def _anonymize_message(self, message: Any) -> Any:
        """Return a copy of *message* with PII anonymized."""
        if isinstance(message, (HumanMessage, AIMessage, SystemMessage, ToolMessage)):
            if isinstance(message.content, str):
                new_content = self.anonymize(message.content)
            elif isinstance(message.content, list):
                new_content = [
                    {**block, "text": self.anonymize(block["text"])}
                    if isinstance(block, dict) and "text" in block
                    else block
                    for block in message.content
                ]
            else:
                return message

            kwargs: dict[str, Any] = {"content": new_content}
            if hasattr(message, "tool_calls") and message.tool_calls:
                kwargs["tool_calls"] = [
                    {
                        **tc,
                        "args": {
                            k: self.anonymize(v) if isinstance(v, str) else v
                            for k, v in tc["args"].items()
                        },
                    }
                    for tc in message.tool_calls
                ]
            if hasattr(message, "tool_call_id") and message.tool_call_id:
                kwargs["tool_call_id"] = message.tool_call_id
            if hasattr(message, "name") and message.name:
                kwargs["name"] = message.name
            if hasattr(message, "id") and message.id:
                kwargs["id"] = message.id

            return type(message)(**kwargs)

        return message


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email to a given address."""
    logger.info(f"\n[EMAIL SENT] To: {to} | Subject: {subject}\n{body}\n")
    return f"Email successfully sent to {to}."


@tool
def get_weather(country_or_city: str) -> str:
    """Get the current weather for a given country or city."""
    return f"The weather in {country_or_city} is 22°C and sunny."


# ---------------------------------------------------------------------------
# Middleware setup
# ---------------------------------------------------------------------------

pii_middleware = PIIAnonymizationMiddleware(
    analyzed_fields=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "LOCATION"],
    language="fr",
    spacy_model="fr_core_news_lg",
    # Optional: add custom regex patterns (e.g. French SSN "NIR")
    extra_patterns=[
        (
            "FR_SSN",
            r"\d{1}\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{3}\s?\d{3}\s?\d{2}",
            "French NIR",
        ),
        (
            "EMAIL_ADDRESS",
            r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
            "Email address",
        ),
        (
            "PHONE_NUMBER",
            r"(?:(?:\+|00)33[\s.\-]?|0)[1-9](?:[\s.\-]?\d{2}){4}",
            "French phone number",
        ),
    ],
)

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

graph = create_agent(
    model="gpt-5",
    system_prompt="""You are a helpful assistant. Some inputs may contain anonymized tokens
(e.g. <LOCATION:a1b2c3>, <PERSON:x9y8z7>, <EMAIL_ADDRESS:d4e5f6>) that replace real values for privacy reasons.

Rules:
1. Treat every token as if it were the real value — never comment on its format,
   never say it's a token, never ask the user to reveal it.
2. A confidential data (placeholder/token) can be use by tools, just use tools normally with the token as input (e.g. get_weather(<LOCATION:a1b2c3>)).
3. If a tool fails or returns no result because the token is unresolvable,
   give a short, natural explanation — one sentence max — without technical jargon.
   Example: "Je ne peux pas dire dans quel pays ce situe la ville '<LOCATION:a1b2c3>' car cette donnée est anonymisée pour protéger vos informations personnelles."
4. Never expose internal reasoning about anonymization to the user.
5. If the user asks for a specific detail about a token (e.g. "what's the first letter?"),
   reply briefly: "Je ne peux pas répondre à cette question car les données ont été anonymisées pour protéger vos données personnelles."
   """,
    tools=[send_email, get_weather],
    middleware=[pii_middleware],
)

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    load_dotenv()
    user_input = (
        "Envoie un email à Jean Dupont (jean.dupont@example.com) "
        "pour lui dire qu'il fait beau à Bordeaux. "
        "Son numéro est 06 12 34 56 78."
        "Pourras tu a la fin me dire par quel lettre commence l'email, le nom prénom, et le dernier numéro de téléphone ? (je vérifie que l'anonymisation fonctionne)"
    )

    # --- What the user typed (raw) ---
    print("=" * 60)
    print("USER INPUT (raw):")
    print(user_input)
    print("=" * 60)

    # --- Anonymize preview (what the LLM will see) ---
    print("\nLLM SEES (anonymized):")
    print(pii_middleware.anonymize(user_input))
    print()

    # --- Mapping ---
    print("MAPPING (token → original):")
    for token, original in pii_middleware.mapping.items():
        print(f"  {token}  →  {original}")
    print()

    # --- Invoke the agent ---
    result = graph.invoke({"messages": [HumanMessage(user_input)]})

    # --- What the user sees (deanonymized by after_agent) ---
    print("=" * 60)
    print("USER SEES (deanonymized):")
    print(result["messages"][-1].content)
    print("=" * 60)
