"""PII anonymization middleware backed by GLiNER2 zero-shot NER."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Awaitable, Callable

from gliner2 import GLiNER2
from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    ModelRequest,
    ModelResponse,
)
from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolCall
from langgraph.runtime import Runtime
from langgraph.types import Command
from loguru import logger

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"<[A-Z_]+:[0-9a-f]{8}>")

# Maps GLiNER label → Presidio-style entity type used in tokens.
_ENTITY_LABELS: dict[str, str] = {
    "person": "PERSON",
    "location": "LOCATION",
    "organization": "ORGANIZATION",
    "email address": "EMAIL_ADDRESS",
    "phone number": "PHONE_NUMBER",
}

_DEFAULT_FIELDS: list[str] = list(_ENTITY_LABELS.values())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _short_hash(value: str) -> str:
    """Return the first 8 hex characters of the SHA-256 digest of *value*.

    Args:
        value: The string to hash.

    Returns:
        An 8-character lowercase hex string.
    """
    return hashlib.sha256(value.encode()).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class PIIAnonymizationMiddleware(AgentMiddleware):
    """Anonymize PII in LLM calls using GLiNER2 zero-shot named entity recognition.

    Every message sent to the model has PII replaced by deterministic placeholder
    tokens (e.g. ``<PERSON:a1b2c3d4>``).  Tool arguments are deanonymized before
    execution so tools receive real values.  The final agent response is
    deanonymized before being returned to the user.

    The mapping is **deterministic per value**: the same original string always
    produces the same token, so the LLM can reason about identity across turns
    without ever seeing real data.

    Example:
        .. code-block:: python

            from aegra.middleware import PIIAnonymizationMiddleware
            from langchain.agents import create_agent

            graph = create_agent(
                model="openai:gpt-4o",
                tools=[...],
                middleware=[PIIAnonymizationMiddleware()],
            )
    """

    def __init__(
        self,
        analyzed_fields: list[str] | None = None,
        gliner_model: str = "fastino/gliner2-large-v1",
        threshold: float = 0.4,
        language: str = "fr",
    ) -> None:
        """Initialize the middleware.

        Args:
            analyzed_fields: Entity types to detect and anonymize.  Defaults to
                ``PERSON``, ``LOCATION``, ``ORGANIZATION``, ``EMAIL_ADDRESS``,
                and ``PHONE_NUMBER``.
            gliner_model: HuggingFace model ID for GLiNER2.
            threshold: Minimum confidence score for an entity to be anonymized.
                Lower values catch more entities but increase false positives.
            language: Language code passed to the NER model (e.g. ``"fr"``,
                ``"en"``).
        """
        super().__init__()

        self._language = language
        self._threshold = threshold
        self._analyzed_fields = analyzed_fields or _DEFAULT_FIELDS

        # Only pass labels whose entity type is requested.
        self._labels: list[str] = [
            label
            for label, entity in _ENTITY_LABELS.items()
            if entity in self._analyzed_fields
        ]

        logger.info("Loading GLiNER2 model: {}", gliner_model)
        self._model: GLiNER2 = GLiNER2.from_pretrained(gliner_model)

        # Bidirectional mapping: original value ↔ anonymized token.
        self._to_token: dict[str, str] = {}
        self._to_original: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def mapping(self) -> dict[str, str]:
        """A copy of the current token → original mapping.

        Returns:
            Dictionary mapping each active token to its original string.
        """
        return dict(self._to_original)

    def anonymize(self, text: str) -> str:
        """Detect PII in *text* and replace each span with a deterministic token.

        The method is idempotent: passing already-tokenized text will not create
        nested tokens such as ``<LOCATION:<LOCATION:...>>``.

        Args:
            text: Raw text potentially containing PII.

        Returns:
            Text with all detected PII replaced by ``<ENTITY_TYPE:xxxxxxxx>``
            tokens.
        """
        if not text or not self._labels:
            return text

        # 1. Replace already-known original values using the existing mapping.
        for original, token in self._to_token.items():
            text = text.replace(original, token)

        # 2. Mask existing tokens with null-byte placeholders so GLiNER cannot
        #    re-detect them and create nested tokens.
        placeholders: dict[str, str] = {}

        def _mask(m: re.Match) -> str:
            ph = f"\x00{len(placeholders)}\x00"
            placeholders[ph] = m.group(0)
            return ph

        text = _TOKEN_RE.sub(_mask, text)

        # 3. Run GLiNER2 to detect new PII spans.
        raw = self._model.extract_entities(
            text,
            self._labels,
            threshold=self._threshold,
            include_spans=True,
            include_confidence=True,
        )

        # Collect all hits and sort descending by start position so that
        # replacing a later span does not shift the indices of earlier ones.
        hits: list[tuple[int, int, str]] = []
        for label, entities in raw.get("entities", {}).items():
            entity_type = _ENTITY_LABELS.get(label)
            if entity_type is None or entity_type not in self._analyzed_fields:
                continue
            for entity in entities:
                hits.append((entity["start"], entity["end"], entity_type))

        hits.sort(key=lambda h: h[0], reverse=True)

        for start, end, entity_type in hits:
            original = text[start:end]
            token = self._get_or_create_token(original, entity_type)
            text = text[:start] + token + text[end:]

        # 4. Restore masked tokens.
        for ph, token in placeholders.items():
            text = text.replace(ph, token)

        return text

    def deanonymize(self, text: str) -> str:
        """Replace all tokens in *text* with their original values.

        Args:
            text: Text containing ``<ENTITY_TYPE:xxxxxxxx>`` tokens.

        Returns:
            Text with tokens replaced by their original PII values.
        """
        for token, original in self._to_original.items():
            text = text.replace(token, original)
        return text

    # ------------------------------------------------------------------
    # Middleware hooks
    # ------------------------------------------------------------------

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Anonymize all messages before they reach the LLM.

        Args:
            request: The outbound model request containing messages and an
                optional system message.
            handler: Callable that forwards the request to the LLM.

        Returns:
            The model response (messages stay anonymized in state; deanonymization
            happens in ``after_agent``).
        """
        anonymized_messages = [self._anonymize_message(m) for m in request.messages]

        anonymized_system = request.system_message
        if request.system_message and request.system_message.content:
            raw = (
                request.system_message.content
                if isinstance(request.system_message.content, str)
                else str(request.system_message.content)
            )
            anonymized_system = SystemMessage(content=self.anonymize(raw))

        return handler(
            request.override(
                messages=anonymized_messages,
                system_message=anonymized_system,
            )
        )

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Async version of :meth:`wrap_model_call`.

        Args:
            request: The outbound model request.
            handler: Async callable that forwards the request to the LLM.

        Returns:
            The model response.
        """
        anonymized_messages = [self._anonymize_message(m) for m in request.messages]

        anonymized_system = request.system_message
        if request.system_message and request.system_message.content:
            raw = (
                request.system_message.content
                if isinstance(request.system_message.content, str)
                else str(request.system_message.content)
            )
            anonymized_system = SystemMessage(content=self.anonymize(raw))

        return await handler(
            request.override(
                messages=anonymized_messages,
                system_message=anonymized_system,
            )
        )

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """Deanonymize tool arguments before execution, then re-anonymize the result.

        Args:
            request: The tool call request with (potentially tokenized) arguments.
            handler: Callable that executes the tool.

        Returns:
            A ``ToolMessage`` with anonymized content, or a ``Command`` unchanged.
        """
        deanonymized_args: dict[str, Any] = {
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

        result = handler(new_request)

        if isinstance(result, ToolMessage):
            content = (
                result.content
                if isinstance(result.content, str)
                else str(result.content)
            )
            return ToolMessage(
                content=self.anonymize(content),
                tool_call_id=result.tool_call_id,
                name=result.name,
            )

        return result

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """Async version of :meth:`wrap_tool_call`.

        Args:
            request: The tool call request.
            handler: Async callable that executes the tool.

        Returns:
            A ``ToolMessage`` with anonymized content, or a ``Command`` unchanged.
        """
        deanonymized_args: dict[str, Any] = {
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
            content = (
                result.content
                if isinstance(result.content, str)
                else str(result.content)
            )
            return ToolMessage(
                content=self.anonymize(content),
                tool_call_id=result.tool_call_id,
                name=result.name,
            )

        return result

    def after_agent(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Deanonymize the final assistant message so the user sees real values.

        Args:
            state: The agent state after the last LLM call.
            runtime: The LangGraph runtime (unused but required by the hook API).

        Returns:
            A state patch with the deanonymized last message, or ``None`` if no
            deanonymization was needed.
        """
        messages = state.get("messages")
        if not messages:
            return None

        last = messages[-1]
        if not isinstance(last, AIMessage):
            return None

        if not isinstance(last.content, str):
            return None

        deanonymized = self.deanonymize(last.content)
        if deanonymized == last.content:
            return None

        return {
            "messages": [
                AIMessage(
                    content=deanonymized,
                    tool_calls=last.tool_calls if hasattr(last, "tool_calls") else [],
                    id=last.id,
                )
            ]
        }

    async def aafter_agent(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Async version of :meth:`after_agent`.

        Args:
            state: The agent state after the last LLM call.
            runtime: The LangGraph runtime.

        Returns:
            A state patch with the deanonymized last message, or ``None``.
        """
        return self.after_agent(state, runtime)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_or_create_token(self, original: str, entity_type: str) -> str:
        """Return the deterministic token for *original*, creating it if needed.

        Args:
            original: The raw PII string (e.g. ``"Jean Dupont"``).
            entity_type: The entity category (e.g. ``"PERSON"``).

        Returns:
            A token of the form ``<ENTITY_TYPE:xxxxxxxx>``.
        """
        if original in self._to_token:
            return self._to_token[original]

        token = f"<{entity_type}:{_short_hash(original)}>"
        self._to_token[original] = token
        self._to_original[token] = original
        return token

    def _anonymize_message(self, message: Any) -> Any:
        """Return a copy of *message* with all PII anonymized.

        ``AIMessage`` instances are returned unchanged — they were produced by the
        model and already contain only tokens.

        Args:
            message: A LangChain message object.

        Returns:
            A new message of the same type with PII replaced, or the original
            message if no transformation was needed.
        """
        # AI messages already contain tokens — skip to avoid wasted work.
        if isinstance(message, AIMessage):
            return message

        if not isinstance(message, (HumanMessage, SystemMessage, ToolMessage)):
            return message

        if isinstance(message.content, str):
            new_content: Any = self.anonymize(message.content)
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
