"""Claude Code hooks integration for transparent PII de-identification.

Wire piighost into Claude Code's hook lifecycle, keyed by the session id as the
anonymization thread. A tool output is anonymized before the model reads it, and
a tool input the model produced is restored to its real values before the tool
runs, so files and commands act on real data while the model only handles tokens
for what tools return. Unlike the proxy this needs no transport interception, so
it works on a subscription.

Claude Code lets no hook replace the user prompt, so the prompt and the files it
mentions with @ reach the model in clear. The UserPromptSubmit hook only gates
the turn, failing when the server cannot be reached. No hook can rewrite the
assistant's displayed reply either, which therefore still shows tokens.

handle_hook is pure: it takes any AnyThreadPipeline, a local pipeline or a remote
PIIGhostClient, so it is driven the same way in tests and in the runner.
"""

from typing import Any

from piighost.conversation_memory.base import MessageRole
from piighost.exceptions import MissingThreadIdError
from piighost.integrations._deidentify import StringOp, map_strings
from piighost.pipeline import AnyThreadPipeline

_TOOL_OUTPUT_TEXT_FIELDS: dict[str, tuple[str, ...]] = {
    "Bash": ("stdout", "stderr"),
    "Read": ("file.content",),
    "Write": ("content", "originalFile", "structuredPatch[].lines[]"),
    "Edit": ("oldString", "newString", "originalFile", "structuredPatch[].lines[]"),
    "Agent": ("content[].text",),
    "Grep": ("content",),
    "WebFetch": ("result",),
    "WebSearch": ("results[].content[].title",),
    "ToolSearch": ("query",),
}
"""Per-tool dotted paths of a structured tool_response that carry model-facing text.

Derived from observed Claude Code tool results: only these leaves hold free text
that can contain PII. Everything else (paths, urls, base64, shas, ids, line
numbers, counts, flags) is metadata the tool and model need verbatim, so it is
left untouched. A `[]` segment descends into every element of a list. A tool not
listed here is passed through so its metadata is never mangled.

Grep keeps its matching lines in content, in content mode, and only file paths in
filenames, which stays untouched."""

_MCP_TOOL_PREFIX = "mcp__"
"""The name prefix of an MCP tool, whose output Claude Code does not validate."""


def _output(event_name: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Wrap a mutation in the hookSpecificOutput envelope Claude Code expects."""
    return {"hookSpecificOutput": {"hookEventName": event_name, **fields}}


async def _apply_path(node: Any, segments: list[str], op: StringOp) -> Any:
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


async def _map_fields(
    data: dict[str, Any], paths: tuple[str, ...], op: StringOp
) -> dict[str, Any]:
    """Apply op to every allowlisted field path in a structured tool result.

    A dotted path splits into segments, each [] list marker its own, so
    "structuredPatch[].lines[]" reads as ["structuredPatch", "[]", "lines", "[]"].
    """
    result: Any = data
    for path in paths:
        segments = path.replace("[]", ".[]").split(".")
        result = await _apply_path(result, segments, op)
    return result


async def _rewrite_tool_output(event: dict[str, Any], op: StringOp) -> Any | None:
    """Return the event's tool output with op applied to its text, or None.

    A plain-string output is rewritten whole. A structured output is rewritten in
    the text fields listed for its tool, keeping the rest of its shape. A tool not
    listed, or an output of another shape, gives None.
    """
    tool_output = event.get("tool_response")
    if isinstance(tool_output, str):
        return await op(tool_output)
    tool_name = event.get("tool_name")
    fields = (
        _TOOL_OUTPUT_TEXT_FIELDS.get(tool_name) if isinstance(tool_name, str) else None
    )
    if isinstance(tool_output, dict) and fields is not None:
        return await _map_fields(tool_output, fields, op)
    return None


async def withhold_tool_output(event: dict[str, Any], notice: str) -> Any | None:
    """Return a PostToolUse event's tool output with its text replaced by notice.

    Claude Code ignores a replacement that does not match a built-in tool's output
    shape and sends the original output instead. So the notice takes the place of
    every listed text field, and the rest of the shape stays as it is. An MCP
    tool's output, which Claude Code does not validate, becomes the notice itself.
    An unlisted built-in tool or an unexpected shape has no replacement Claude
    Code would honour, so it gives None.
    """

    async def to_notice(_: str) -> str:
        return notice

    withheld = await _rewrite_tool_output(event, to_notice)
    tool_name = event.get("tool_name")
    if (
        withheld is None
        and isinstance(tool_name, str)
        and tool_name.startswith(_MCP_TOOL_PREFIX)
    ):
        return notice
    return withheld


async def handle_hook(
    event: dict[str, Any], pipeline: AnyThreadPipeline
) -> dict[str, Any] | None:
    """Return the mutation for one Claude Code hook event, or None to pass through.

    Dispatches on hook_event_name. PostToolUse anonymizes the tool output the
    model is about to read, and PreToolUse restores the real values in a tool input
    the model produced. UserPromptSubmit anonymizes the prompt only to record its
    values in the thread and to fail when the server cannot be reached. It returns
    no mutation, since Claude Code lets no hook replace the prompt. The session id
    is the anonymization thread, and an event without one raises
    MissingThreadIdError. An event without its payload field, or one this
    integration does not handle, is a no-op.
    """
    name = event.get("hook_event_name")
    thread_id = event.get("session_id")
    if not isinstance(thread_id, str) or not thread_id:
        raise MissingThreadIdError(
            "The hook event carries no session_id, the thread its values belong to."
        )

    if name == "UserPromptSubmit":
        prompt = event.get("prompt")
        if isinstance(prompt, str):
            await pipeline.anonymize(prompt, thread_id, role=MessageRole.USER)
        return None

    if name == "PostToolUse":

        async def anonymize_text(text: str) -> str:
            result = await pipeline.anonymize(text, thread_id, role=MessageRole.USER)
            return result.text

        updated = await _rewrite_tool_output(event, anonymize_text)
        if updated is None:
            # Unknown tool or unexpected shape: pass through, the debug log keeps it.
            return None
        return _output(name, {"updatedToolOutput": updated})

    if name == "PreToolUse":
        tool_input = event.get("tool_input")
        if not isinstance(tool_input, dict):
            return None

        async def restore(text: str) -> str:
            return await pipeline.deanonymize(text, thread_id)

        restored = await map_strings(tool_input, restore)
        return _output(name, {"updatedInput": restored})

    return None
