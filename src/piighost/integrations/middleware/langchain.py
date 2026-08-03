"""LangChain middleware for transparent PII anonymization (optional: langchain).

It anonymizes messages before the model sees them and deanonymizes the model's
output for display, delegating all detection, token assignment, and replacement
to a ThreadAnonymizationPipeline. This module needs the langchain package; it is
guarded so importing it without the dependency raises an ImportError pointing at
the extra to install.
"""

import importlib.util
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Generic

from typing_extensions import TypeVar

from piighost.components.placeholder.base import BaseDelimitedPlaceholderFactory
from piighost.components.placeholder.tags import PreservesIdentity
from piighost.exceptions import InventedPlaceholderError
from piighost.integrations.middleware.strategy import (
    InventedPlaceholderStrategy,
    ToolCallStrategy,
)
from piighost.pipeline import ThreadAnonymizationPipeline

if importlib.util.find_spec("langchain") is None:
    raise ImportError(
        "PIIAnonymizationMiddleware requires the langchain package. "
        "Install it with: pip install piighost[middleware]"
    )

from langchain.agents.middleware import AgentMiddleware, AgentState  # noqa: E402
from langchain_core.messages import (  # noqa: E402
    AIMessage,
    HumanMessage,
    ToolMessage,
)
from langgraph.config import get_config  # noqa: E402
from langgraph.prebuilt.tool_node import ToolCallRequest  # noqa: E402
from langgraph.runtime import Runtime  # noqa: E402
from langgraph.types import Command  # noqa: E402

logger = logging.getLogger(__name__)

_DEFAULT_THREAD = "default"
_missing_thread_id_warned = False

IdentityT = TypeVar("IdentityT", bound=PreservesIdentity, default=PreservesIdentity)


def _thread_id(require_thread_id: bool) -> str:
    """Return the thread id from the LangGraph config.

    Without one, every conversation would share a thread and leak placeholders.
    With require_thread_id, a missing id is an error; otherwise it warns once and
    falls back to a shared default thread, because get_config does not surface the
    id reliably across LangGraph versions.
    """
    global _missing_thread_id_warned

    try:
        thread_id = get_config().get("configurable", {}).get("thread_id")
    except RuntimeError:
        thread_id = None

    if thread_id is not None:
        return thread_id

    if require_thread_id:
        raise ValueError(
            "No thread_id in the LangGraph config and require_thread_id=True; "
            "pass config={'configurable': {'thread_id': ...}} on the agent call."
        )

    if not _missing_thread_id_warned:
        _missing_thread_id_warned = True
        logger.warning(
            "No thread_id in the LangGraph config; falling back to the shared "
            "'default' thread, so distinct conversations share placeholder "
            "state. Pass a thread_id or set require_thread_id=True."
        )

    return _DEFAULT_THREAD


class PIIAnonymizationMiddleware(AgentMiddleware, Generic[IdentityT]):
    """Anonymize PII around the model and tool boundary of a LangChain agent.

    A thin adapter: it reads the thread id from the LangGraph config, anonymizes
    the user and model messages before the model call, deanonymizes them after
    for display, and routes tool calls by the chosen strategy. The pipeline's
    tokens must preserve identity, so deanonymization is unambiguous; this is
    enforced at type-check time by the IdentityT bound.

    Attributes:
        tool_strategy: How tool calls are handled.
    """

    def __init__(
        self,
        pipeline: ThreadAnonymizationPipeline[IdentityT],
        tool_strategy: ToolCallStrategy = ToolCallStrategy.FULL,
        require_thread_id: bool = True,
        invented_strategy: InventedPlaceholderStrategy = InventedPlaceholderStrategy.RAISE,
    ) -> None:
        """Store the pipeline, the strategies, and the thread-id policy.

        require_thread_id defaults to True so a missing thread id raises rather
        than routing every conversation into the shared default thread and
        leaking placeholders across them. Pass False to opt into that shared
        fallback knowingly, for single-conversation or stateless use.

        invented_strategy defaults to RAISE so a token the pipeline never issued,
        surfacing in a deanonymized model reply or tool argument, is refused
        rather than passed on. Pass KEEP or DROP to tolerate it instead.
        """
        super().__init__()
        self._pipeline = pipeline
        self.tool_strategy = tool_strategy
        self._require_thread_id = require_thread_id
        self._invented_strategy = invented_strategy

    async def abefore_model(
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        """Anonymize the user and model messages before the model sees them."""
        thread_id = _thread_id(self._require_thread_id)
        allowed: tuple[type, ...] = (HumanMessage, AIMessage)

        if self.tool_strategy is ToolCallStrategy.INPUT:
            # INPUT left the tool response raw, so anonymize it here before the
            # model sees it, unlike OUTPUT/FULL which already anonymized it.
            allowed = (HumanMessage, AIMessage, ToolMessage)

        return await self._rewrite(
            state,
            allowed,
            lambda text: self._anonymize(text, thread_id),
        )

    async def aafter_model(
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        """Deanonymize the user and model messages for display."""
        thread_id = _thread_id(self._require_thread_id)

        return await self._rewrite(
            state,
            (HumanMessage, AIMessage),
            lambda text: self._deanonymize(text, thread_id),
        )

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        """Route the tool call by strategy: deanonymize args, anonymize result."""
        strategy = self.tool_strategy

        if strategy is ToolCallStrategy.PASSTHROUGH:
            return await handler(request)

        thread_id = _thread_id(self._require_thread_id)
        deanonymize_input = strategy in (ToolCallStrategy.INPUT, ToolCallStrategy.FULL)
        anonymize_output = strategy in (ToolCallStrategy.OUTPUT, ToolCallStrategy.FULL)

        if deanonymize_input:
            call = request.tool_call
            call["args"] = await self._deanonymize_value(call["args"], thread_id)

        response = await handler(request)

        if anonymize_output and (
            isinstance(response, ToolMessage) and isinstance(response.content, str)
        ):
            response.content = await self._anonymize(response.content, thread_id)

        return response

    async def _rewrite(
        self,
        state: AgentState,
        allowed: tuple[type, ...],
        transform: Callable[[str], Awaitable[str]],
    ) -> dict[str, Any] | None:
        """Apply transform to each allowed message's text, in place."""
        changed = False
        messages = state["messages"]

        for message in messages:
            content = message.content
            if not isinstance(message, allowed) or not isinstance(content, str):
                continue

            rewritten = await transform(content)
            if rewritten != content:
                message.content = rewritten
                changed = True

        return {"messages": messages} if changed else None

    async def _anonymize(self, text: str, thread_id: str) -> str:
        """Anonymize a text within the thread and return the anonymized string."""
        result = await self._pipeline.anonymize(text, thread_id)
        return result.text

    async def _deanonymize(self, text: str, thread_id: str) -> str:
        """Deanonymize a text, then apply the invented-placeholder strategy."""
        restored = await self._pipeline.deanonymize(text, thread_id)
        return self._handle_invented(restored)

    def _handle_invented(self, text: str) -> str:
        """Apply the invented-placeholder strategy to already deanonymized text.

        Every issued token was replaced during deanonymization, so any token
        still matching the factory's grammar was invented by the model. KEEP
        leaves it, DROP removes it, RAISE refuses it. A factory with no
        recognizable grammar, such as a mask, has no tokens to find, so the text
        returns unchanged.
        """
        factory = getattr(self._pipeline.anonymizer, "factory", None)
        if not isinstance(factory, BaseDelimitedPlaceholderFactory):
            return text

        invented = factory.find_tokens(text)
        if not invented or self._invented_strategy is InventedPlaceholderStrategy.KEEP:
            return text

        if self._invented_strategy is InventedPlaceholderStrategy.RAISE:
            raise InventedPlaceholderError(
                f"Deanonymized text holds tokens the pipeline never issued: {invented}",
                invented,
            )

        cleaned = text
        for token in invented:
            cleaned = cleaned.replace(token, "")
        return cleaned

    async def _deanonymize_value(self, value: Any, thread_id: str) -> Any:
        """Deanonymize strings inside nested dict, list, and tuple containers."""
        if isinstance(value, str):
            return await self._deanonymize(value, thread_id)
        if isinstance(value, dict):
            return {
                key: await self._deanonymize_value(item, thread_id)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            items = [await self._deanonymize_value(item, thread_id) for item in value]
            return tuple(items) if isinstance(value, tuple) else items
        return value
