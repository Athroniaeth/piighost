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

_TOOL_OUTPUT_TEXT_FIELDS: dict[str, tuple[str, ...]] = {
    "Bash": ("stdout", "stderr"),
    "Read": ("file.content",),
    "Write": ("content", "originalFile", "structuredPatch[].lines[]"),
    "Edit": ("oldString", "newString", "originalFile", "structuredPatch[].lines[]"),
    "Agent": ("content[].text",),
    "WebFetch": ("result",),
    "WebSearch": ("results[].content[].title",),
    "ToolSearch": ("query",),
}
"""Per-tool dotted paths of a structured tool_response that carry model-facing text.

Derived from observed Claude Code tool results: only these leaves hold free text
that can contain PII. Everything else (paths, urls, base64, shas, ids, line
numbers, counts, flags) is metadata the tool and model need verbatim, so it is
left untouched. A `[]` segment descends into every element of a list. A tool not
listed here is passed through so its metadata is never mangled."""


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


def _split_path(path: str) -> list[str]:
    """Split a dotted field path into segments, expanding each `[]` list marker.

    "structuredPatch[].lines[]" becomes ["structuredPatch", "[]", "lines", "[]"].
    """
    segments: list[str] = []
    for part in path.split("."):
        name = part
        markers = 0
        while name.endswith("[]"):
            name = name[:-2]
            markers += 1
        if name:
            segments.append(name)
        segments.extend(["[]"] * markers)
    return segments


async def _apply_path(node: Any, segments: list[str], op: _StringOp) -> Any:
    """Return node with op applied to the string leaves reached by segments.

    Rebuilds only the nodes along the path, sharing untouched siblings. A segment
    or list element that does not exist leaves the node unchanged.
    """
    if not segments:
        return await op(node) if isinstance(node, str) else node
    head, rest = segments[0], segments[1:]
    if head == "[]":
        if isinstance(node, list):
            return [await _apply_path(item, rest, op) for item in node]
        return node
    if isinstance(node, dict) and head in node:
        updated = dict(node)
        updated[head] = await _apply_path(node[head], rest, op)
        return updated
    return node


async def _anonymize_fields(
    data: dict[str, Any], paths: tuple[str, ...], op: _StringOp
) -> dict[str, Any]:
    """Apply op to every allowlisted field path in a structured tool result."""
    result: Any = data
    for path in paths:
        result = await _apply_path(result, _split_path(path), op)
    return result


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

        async def anonymize_text(text: str) -> str:
            result = await pipeline.anonymize(text, thread_id, role=MessageRole.USER)
            return result.text

        if isinstance(tool_output, str):
            return _output(
                name, {"updatedToolOutput": await anonymize_text(tool_output)}
            )
        tool_name = event.get("tool_name")
        fields = (
            _TOOL_OUTPUT_TEXT_FIELDS.get(tool_name)
            if isinstance(tool_name, str)
            else None
        )
        if isinstance(tool_output, dict) and fields is not None:
            updated = await _anonymize_fields(tool_output, fields, anonymize_text)
            return _output(name, {"updatedToolOutput": updated})
        # Unknown tool or unexpected shape: pass through, capture it to learn it.
        return None

    if name == "PreToolUse":
        tool_input = event.get("tool_input")
        if not isinstance(tool_input, dict):
            return None

        async def restore(text: str) -> str:
            return await pipeline.deanonymize(text, thread_id)

        restored = await _map_strings(tool_input, restore)
        return _output(name, {"updatedInput": restored})

    return None
