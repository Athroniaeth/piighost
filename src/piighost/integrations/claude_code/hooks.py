"""Claude Code hooks integration for transparent PII de-identification.

Wire piighost into Claude Code's hook lifecycle, keyed by the session id as the
anonymization thread. The user prompt and tool outputs are anonymized before the
model reads them, and a tool input the model produced is restored to its real
values before the tool runs, so files and commands act on real data while the
model only ever handles tokens. Unlike the proxy this needs no transport
interception, so it works on a subscription. The one gap is that no hook can
rewrite the assistant's displayed reply, which therefore still shows tokens.

handle_hook is pure: it takes any AnyThreadPipeline, a local pipeline or a remote
PIIGhostClient, so it is driven the same way in tests and in the runner.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from piighost.conversation_memory.base import MessageRole
from piighost.pipeline import AnyThreadPipeline

_StringOp = Callable[[str], Awaitable[str]]


def _output(event_name: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Wrap a mutation in the hookSpecificOutput envelope Claude Code expects."""
    return {"hookSpecificOutput": {"hookEventName": event_name, **fields}}


async def _map_strings(value: Any, op: _StringOp) -> Any:
    """Apply op to every string inside nested dicts and lists."""
    if isinstance(value, str):
        return await op(value)
    if isinstance(value, dict):
        return {key: await _map_strings(item, op) for key, item in value.items()}
    if isinstance(value, list):
        return [await _map_strings(item, op) for item in value]
    return value


async def handle_hook(
    event: dict[str, Any], pipeline: AnyThreadPipeline
) -> dict[str, Any] | None:
    """Return the mutation for one Claude Code hook event, or None to pass through.

    Dispatches on hook_event_name. UserPromptSubmit and PostToolUse anonymize the
    text the model is about to read; PreToolUse restores the real values in a tool
    input the model produced. The session id is the anonymization thread. An event
    without its payload field, or one this integration does not handle, is a no-op.
    """
    name = event.get("hook_event_name")
    thread_id = event.get("session_id") or "default"

    if name == "UserPromptSubmit":
        prompt = event.get("prompt")
        if not isinstance(prompt, str):
            return None
        anonymized = await pipeline.anonymize(prompt, thread_id, role=MessageRole.USER)
        return _output(name, {"updatedPrompt": anonymized.text})

    if name == "PostToolUse":
        tool_output = event.get("tool_response")
        if not isinstance(tool_output, str):
            # Structured tool outputs are passed through untouched for now.
            return None
        anonymized = await pipeline.anonymize(
            tool_output, thread_id, role=MessageRole.USER
        )
        return _output(name, {"updatedToolOutput": anonymized.text})

    if name == "PreToolUse":
        tool_input = event.get("tool_input")
        if not isinstance(tool_input, dict):
            return None

        async def restore(text: str) -> str:
            return await pipeline.deanonymize(text, thread_id)

        restored = await _map_strings(tool_input, restore)
        return _output(name, {"updatedInput": restored})

    return None
