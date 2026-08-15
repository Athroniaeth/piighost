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

from piighost.components.placeholder.tags import PreservesRecognizableIdentity
from piighost.conversation_memory import MessageRole
from piighost.exceptions import MissingThreadIdError
from piighost.integrations._deidentify import TextDeidentifier
from piighost.integrations.middleware.strategy import (
    AssistantEntityStrategy,
    InventedPlaceholderStrategy,
    ToolCallStrategy,
)
from piighost.pipeline import AnyThreadPipeline

if importlib.util.find_spec("langchain") is None:
    raise ImportError(
        "PIIAnonymizationMiddleware requires the langchain package. "
        "Install it with: pip install piighost[middleware]"
    )

from langchain.agents.middleware import AgentMiddleware, AgentState  # noqa: E402
from langchain_core.messages import (  # noqa: E402
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from langgraph.config import get_config  # noqa: E402
from langgraph.prebuilt.tool_node import ToolCallRequest  # noqa: E402
from langgraph.runtime import Runtime  # noqa: E402
from langgraph.types import Command  # noqa: E402

logger = logging.getLogger(__name__)

_DEFAULT_THREAD = "default"
"""Shared fallback thread id used when no thread id is present.

Falling back to it lets distinct conversations share placeholder state, which
leaks entities across them; require_thread_id exists to reject that fallback.
"""
_missing_thread_id_warned = False

IdentityT = TypeVar(
    "IdentityT",
    bound=PreservesRecognizableIdentity,
    default=PreservesRecognizableIdentity,
)


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
        raise MissingThreadIdError(
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
    tokens must preserve identity, so deanonymization is unambiguous, and carry a
    delimited grammar, so a token the model invented can be found and refused;
    both are required at type-check time by the IdentityT bound, which narrows on
    PreservesRecognizableIdentity, and re-checked at construction.

    Attributes:
        tool_strategy: How tool calls are handled.
    """

    def __init__(
        self,
        pipeline: AnyThreadPipeline[IdentityT],
        tool_strategy: ToolCallStrategy = ToolCallStrategy.FULL,
        require_thread_id: bool = True,
        invented_strategy: InventedPlaceholderStrategy = InventedPlaceholderStrategy.RAISE,
        assistant_strategy: AssistantEntityStrategy = AssistantEntityStrategy.PRESERVE,
    ) -> None:
        """Store the pipeline, the strategies, and the thread-id policy.

        require_thread_id defaults to True so a missing thread id raises rather
        than routing every conversation into the shared default thread and
        leaking placeholders across them. Pass False to opt into that shared
        fallback knowingly, for single-conversation or stateless use.

        invented_strategy defaults to RAISE so a token the pipeline never issued,
        surfacing in a deanonymized model reply or tool argument, is refused
        rather than passed on. Pass KEEP or DROP to tolerate it instead.

        assistant_strategy defaults to PRESERVE so a value the assistant
        introduced is left in clear, keeping the model's world knowledge of it.
        Pass ANONYMIZE to tokenize it anyway, or IGNORE to skip analyzing
        assistant messages entirely and save the detector.
        """
        super().__init__()
        # The de-identifier holds the pipeline and the invented-placeholder
        # policy, and re-checks the recognizer at construction so an untyped or
        # remote pipeline without one fails loudly here.
        self._deid = TextDeidentifier(pipeline, invented_strategy)
        self.tool_strategy = tool_strategy
        self._require_thread_id = require_thread_id
        self.assistant_strategy = assistant_strategy

    async def abefore_model(
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        """Anonymize the user and model messages before the model sees them."""
        thread_id = _thread_id(self._require_thread_id)
        allowed: tuple[type[BaseMessage], ...] = (HumanMessage, AIMessage)

        if self.assistant_strategy is AssistantEntityStrategy.IGNORE:
            # IGNORE skips assistant analysis entirely, so its messages are not
            # sent through anonymization at all, saving the detector.
            allowed = (HumanMessage,)

        # A tool response is handled only in the tool wrapper, never here, so a
        # ToolMessage is never rewritten by the before-model pass. A strategy
        # that does not anonymize the response therefore leaves it as the tool
        # returned it, and the model sees it that way.

        async def anonymize(message: BaseMessage, content: str) -> str:
            """Anonymize one message under the role its type contributes."""
            role = self._message_role(message)
            return await self._anonymize(content, thread_id, role)

        return await self._rewrite(state, allowed, anonymize)

    async def aafter_model(
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        """Deanonymize the user and model messages for display."""
        thread_id = _thread_id(self._require_thread_id)

        async def restore(message: BaseMessage, content: str) -> str:
            """Deanonymize one message's content for display."""
            return await self._deanonymize(content, thread_id)

        return await self._rewrite(state, (HumanMessage, AIMessage), restore)

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
        allowed: tuple[type[BaseMessage], ...],
        transform: Callable[[BaseMessage, str], Awaitable[str]],
    ) -> dict[str, Any] | None:
        """Apply transform to each allowed message's text, in place."""
        changed = False
        messages = state["messages"]

        for message in messages:
            content = message.content
            if not isinstance(message, allowed) or not isinstance(content, str):
                continue

            rewritten = await transform(message, content)
            if rewritten != content:
                message.content = rewritten
                changed = True

        return {"messages": messages} if changed else None

    def _message_role(self, message: BaseMessage) -> MessageRole:
        """Return the provenance role a message contributes.

        An AIMessage is ASSISTANT under PRESERVE, but USER under ANONYMIZE so its
        values are anonymized like user PII. Everything else counts as USER.
        """
        if not isinstance(message, AIMessage):
            return MessageRole.USER
        if self.assistant_strategy is AssistantEntityStrategy.ANONYMIZE:
            return MessageRole.USER
        return MessageRole.ASSISTANT

    async def _anonymize(
        self, text: str, thread_id: str, role: MessageRole = MessageRole.USER
    ) -> str:
        """Anonymize a text within the thread and return the anonymized string."""
        return await self._deid.anonymize(text, thread_id, role)

    async def _deanonymize(self, text: str, thread_id: str) -> str:
        """Deanonymize a text, applying the invented-placeholder strategy."""
        return await self._deid.deanonymize(text, thread_id)

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
