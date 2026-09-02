"""Pydantic AI capability for transparent PII de-identification (optional: pydantic-ai).

It anonymizes every user and assistant text before the model sees it and
deanonymizes the model's reply for display, delegating detection, token
assignment, and replacement to a ThreadAnonymizationPipeline through the shared
TextDeidentifier. This module needs the pydantic-ai package; it is guarded so
importing it without the dependency raises an ImportError pointing at the extra.
"""

import importlib.util
from collections.abc import Callable
from typing import Any

from typing_extensions import TypeVar

from piighost.components.placeholder.tags import PreservesRecognizableIdentity
from piighost.conversation_memory import MessageRole
from piighost.integrations._deidentify import TextDeidentifier
from piighost.integrations.langchain.strategy import (
    EntityCreateByAssistantStrategy,
    InventedPlaceholderStrategy,
    ToolCallStrategy,
)
from piighost.pipeline import AnyThreadPipeline

if importlib.util.find_spec("pydantic_ai") is None:
    raise ImportError(
        "The Pydantic AI capability requires the pydantic-ai package. "
        "Install it with: pip install piighost[pydantic-ai]"
    )

from pydantic_ai import ModelRequestContext, RunContext
from pydantic_ai.capabilities import Hooks, ValidatedToolArgs
from pydantic_ai.messages import (
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)

IdentityT = TypeVar(
    "IdentityT",
    bound=PreservesRecognizableIdentity,
    default=PreservesRecognizableIdentity,
)


def pii_hooks(
    pipeline: AnyThreadPipeline[IdentityT],
    thread_id: Callable[[RunContext[Any]], str] | str,
    invented_strategy: InventedPlaceholderStrategy = InventedPlaceholderStrategy.RAISE,
    tool_strategy: ToolCallStrategy = ToolCallStrategy.FULL,
    assistant_strategy: EntityCreateByAssistantStrategy = EntityCreateByAssistantStrategy.PRESERVE,
) -> Hooks:
    """Build a Pydantic AI capability that de-identifies PII around the model.

    Register the returned Hooks on an agent with capabilities=[pii_hooks(...)]. It
    anonymizes every user and assistant text the model would see, so the model
    only ever works on placeholders, including across a multi-turn history, and
    deanonymizes the model's reply for display. The thread id is resolved per run
    from thread_id, either a fixed string or a callable over the run context, for
    example lambda ctx: ctx.deps.thread_id.

    tool_strategy governs the tool boundary the same way as the LangChain
    middleware. Under FULL, the default, a tool call's arguments are deanonymized
    before the tool runs, so the tool works on the real values, and the tool's
    string result is re-anonymized after, so the model keeps seeing placeholders.
    INPUT deanonymizes only the arguments, OUTPUT re-anonymizes only the result,
    and PASSTHROUGH leaves both untouched.

    assistant_strategy governs values the assistant introduces, as in the
    LangChain middleware. Under PRESERVE, the default, an assistant text is
    anonymized under the ASSISTANT role, so a value the assistant first
    introduced is left in clear and only known user PII is tokenized. ANONYMIZE
    treats it as USER, tokenizing those values too, and IGNORE skips assistant
    texts entirely, saving the detector.

    The pipeline must expose a recognizable token grammar, or this raises at build
    time through TextDeidentifier. A token the model invents is handled by
    invented_strategy on restore, RAISE by default.
    """
    deid = TextDeidentifier(pipeline, invented_strategy)
    deanonymize_args = tool_strategy in (ToolCallStrategy.INPUT, ToolCallStrategy.FULL)
    anonymize_result = tool_strategy in (ToolCallStrategy.OUTPUT, ToolCallStrategy.FULL)
    skip_assistant = assistant_strategy is EntityCreateByAssistantStrategy.IGNORE
    if assistant_strategy is EntityCreateByAssistantStrategy.ANONYMIZE:
        assistant_role = MessageRole.USER
    else:
        assistant_role = MessageRole.ASSISTANT

    def resolve_thread_id(ctx: RunContext[Any]) -> str:
        """Return the run's thread id from the fixed value or the getter."""
        if isinstance(thread_id, str):
            return thread_id
        return thread_id(ctx)

    async def anonymize_content(content: Any, thread: str, role: MessageRole) -> Any:
        """Anonymize a content that is a string or a sequence of strings.

        The sequence form is the multimodal default. Only the string elements are
        anonymized and the sequence is rebuilt, leaving image and other non-text
        elements untouched, so a block form never slips past in clear.
        """
        if isinstance(content, str):
            return await deid.anonymize(content, thread, role)
        if isinstance(content, (list, tuple)):
            items = [
                await deid.anonymize(item, thread, role)
                if isinstance(item, str)
                else item
                for item in content
            ]
            return items if isinstance(content, list) else tuple(items)
        return content

    hooks = Hooks()

    @hooks.on.before_model_request
    async def anonymize(
        ctx: RunContext[Any], request_context: ModelRequestContext
    ) -> ModelRequestContext:
        """Anonymize every user and assistant text before the model sees it."""
        current_thread = resolve_thread_id(ctx)
        for message in request_context.messages:
            for part in message.parts:
                if isinstance(part, UserPromptPart):
                    part.content = await anonymize_content(
                        part.content, current_thread, MessageRole.USER
                    )
                elif not skip_assistant and isinstance(part, TextPart):
                    part.content = await anonymize_content(
                        part.content, current_thread, assistant_role
                    )
        return request_context

    @hooks.on.after_model_request
    async def deanonymize(
        ctx: RunContext[Any],
        *,
        request_context: ModelRequestContext,
        response: ModelResponse,
    ) -> ModelResponse:
        """Deanonymize the model's reply for display, applying the invented policy."""
        current_thread = resolve_thread_id(ctx)
        for part in response.parts:
            if isinstance(part, TextPart) and isinstance(part.content, str):
                part.content = await deid.deanonymize(part.content, current_thread)
        return response

    @hooks.on.before_tool_execute
    async def deanonymize_tool_args(
        ctx: RunContext[Any],
        *,
        call: ToolCallPart,
        tool_def: Any,
        args: ValidatedToolArgs,
    ) -> ValidatedToolArgs:
        """Deanonymize the tool arguments so the tool works on the real values."""
        if not deanonymize_args:
            return args
        current_thread = resolve_thread_id(ctx)
        return await deid.deanonymize_value(args, current_thread)

    @hooks.on.after_tool_execute
    async def anonymize_tool_result(
        ctx: RunContext[Any],
        *,
        call: ToolCallPart,
        tool_def: Any,
        args: ValidatedToolArgs,
        result: Any,
    ) -> Any:
        """Re-anonymize the tool result so the model keeps seeing placeholders.

        The result is walked recursively, so a structured result, a dict or list
        of strings, is re-anonymized too, not only a plain string one.
        """
        if not anonymize_result:
            return result
        current_thread = resolve_thread_id(ctx)
        return await deid.anonymize_value(result, current_thread)

    return hooks
