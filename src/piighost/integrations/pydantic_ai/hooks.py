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
from piighost.integrations.middleware.strategy import InventedPlaceholderStrategy
from piighost.pipeline import AnyThreadPipeline

if importlib.util.find_spec("pydantic_ai") is None:
    raise ImportError(
        "The Pydantic AI capability requires the pydantic-ai package. "
        "Install it with: pip install piighost[pydantic-ai]"
    )

from pydantic_ai import ModelRequestContext, RunContext  # noqa: E402
from pydantic_ai.capabilities import Hooks  # noqa: E402
from pydantic_ai.messages import ModelResponse, TextPart, UserPromptPart  # noqa: E402

IdentityT = TypeVar(
    "IdentityT",
    bound=PreservesRecognizableIdentity,
    default=PreservesRecognizableIdentity,
)


def pii_hooks(
    pipeline: AnyThreadPipeline[IdentityT],
    thread_id: Callable[[RunContext[Any]], str] | str,
    invented_strategy: InventedPlaceholderStrategy = InventedPlaceholderStrategy.RAISE,
) -> Hooks:
    """Build a Pydantic AI capability that de-identifies PII around the model.

    Register the returned Hooks on an agent with capabilities=[pii_hooks(...)]. It
    anonymizes every user and assistant text the model would see, so the model
    only ever works on placeholders, including across a multi-turn history, and
    deanonymizes the model's reply for display. The thread id is resolved per run
    from thread_id, either a fixed string or a callable over the run context, for
    example lambda ctx: ctx.deps.thread_id.

    The pipeline must expose a recognizable token grammar, or this raises at build
    time through TextDeidentifier. A token the model invents is handled by
    invented_strategy on restore, RAISE by default.
    """
    deid = TextDeidentifier(pipeline, invented_strategy)

    def resolve_thread_id(ctx: RunContext[Any]) -> str:
        """Return the run's thread id from the fixed value or the getter."""
        if isinstance(thread_id, str):
            return thread_id
        return thread_id(ctx)

    hooks = Hooks()

    @hooks.on.before_model_request
    async def anonymize(
        ctx: RunContext[Any], request_context: ModelRequestContext
    ) -> ModelRequestContext:
        """Anonymize every user and assistant text before the model sees it."""
        current_thread = resolve_thread_id(ctx)
        for message in request_context.messages:
            for part in message.parts:
                if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                    part.content = await deid.anonymize(
                        part.content, current_thread, MessageRole.USER
                    )
                elif isinstance(part, TextPart) and isinstance(part.content, str):
                    part.content = await deid.anonymize(
                        part.content, current_thread, MessageRole.ASSISTANT
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

    return hooks
