"""Tests for the Claude Code hooks integration, over a local thread pipeline.

handle_hook takes any AnyThreadPipeline, so these drive it with a real local
ThreadAnonymizationPipeline and an ExactMatchDetector, no server or httpx needed.
"""

import io
import json
from pathlib import Path

import pytest

from piighost.components.detector import ExactMatchDetector
from piighost.integrations.claude_code import handle_hook
from piighost.integrations.claude_code.capture import capture
from piighost.pipeline import ThreadAnonymizationPipeline


def _pipeline() -> ThreadAnonymizationPipeline:
    detector = ExactMatchDetector({"Patrick": "PERSON"})
    return ThreadAnonymizationPipeline(detector)


async def test_user_prompt_submit_anonymizes_prompt() -> None:
    """The submitted prompt is anonymized into updatedPrompt; the model sees a token."""
    pipeline = _pipeline()
    event = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "s1",
        "prompt": "I am Patrick",
    }
    output = await handle_hook(event, pipeline)
    assert output is not None
    specific = output["hookSpecificOutput"]
    assert specific["hookEventName"] == "UserPromptSubmit"
    assert "Patrick" not in specific["updatedPrompt"]
    assert "<<PERSON:1>>" in specific["updatedPrompt"]


async def test_post_tool_use_anonymizes_string_output() -> None:
    """A string tool output is anonymized into updatedToolOutput before the model."""
    pipeline = _pipeline()
    event = {
        "hook_event_name": "PostToolUse",
        "session_id": "s1",
        "tool_name": "Bash",
        "tool_response": "Patrick ran the build",
    }
    output = await handle_hook(event, pipeline)
    assert output is not None
    specific = output["hookSpecificOutput"]
    assert specific["hookEventName"] == "PostToolUse"
    assert "Patrick" not in specific["updatedToolOutput"]
    assert "<<PERSON:1>>" in specific["updatedToolOutput"]


async def test_pre_tool_use_deanonymizes_tool_input() -> None:
    """A tool input carrying a token is restored to the real value before execution."""
    pipeline = _pipeline()
    # Prime the session so <<PERSON:1>> maps back to Patrick.
    await handle_hook(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "s1",
            "prompt": "I am Patrick",
        },
        pipeline,
    )
    event = {
        "hook_event_name": "PreToolUse",
        "session_id": "s1",
        "tool_name": "Bash",
        "tool_input": {"command": "echo <<PERSON:1>>", "timeout": 5},
    }
    output = await handle_hook(event, pipeline)
    assert output is not None
    specific = output["hookSpecificOutput"]
    assert specific["hookEventName"] == "PreToolUse"
    assert specific["updatedInput"]["command"] == "echo Patrick"
    assert specific["updatedInput"]["timeout"] == 5


async def test_unknown_event_is_a_no_op() -> None:
    """An event with no anonymization role returns no mutation."""
    pipeline = _pipeline()
    event = {"hook_event_name": "SessionStart", "session_id": "s1"}
    assert await handle_hook(event, pipeline) is None


async def test_missing_field_is_a_no_op() -> None:
    """A malformed event missing its payload field returns no mutation, not an error."""
    pipeline = _pipeline()
    event = {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    assert await handle_hook(event, pipeline) is None


def test_capture_appends_event_as_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The capture logger appends the raw event as one JSON line, mutating nothing."""
    log = tmp_path / "cap.jsonl"
    monkeypatch.setenv("PIIGHOST_HOOK_LOG", str(log))
    event = {"hook_event_name": "PostToolUse", "tool_response": {"file": {"a": 1}}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(event)))
    capture()
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["tool_response"] == {"file": {"a": 1}}


async def test_post_tool_use_anonymizes_read_content_leaves_path() -> None:
    """A Read result has file.content anonymized while file.filePath is left intact."""
    pipeline = _pipeline()
    event = {
        "hook_event_name": "PostToolUse",
        "session_id": "s1",
        "tool_name": "Read",
        "tool_response": {
            "type": "text",
            "file": {"filePath": "/home/Patrick/notes.txt", "content": "call Patrick"},
        },
    }
    output = await handle_hook(event, pipeline)
    assert output is not None
    updated = output["hookSpecificOutput"]["updatedToolOutput"]
    assert updated["file"]["content"] == "call <<PERSON:1>>"
    # The path is metadata: left verbatim even though it contains the name.
    assert updated["file"]["filePath"] == "/home/Patrick/notes.txt"


async def test_post_tool_use_edit_anonymizes_text_leaves_metadata() -> None:
    """An Edit result anonymizes diff text but leaves filePath and line numbers."""
    pipeline = _pipeline()
    event = {
        "hook_event_name": "PostToolUse",
        "session_id": "s1",
        "tool_name": "Edit",
        "tool_response": {
            "filePath": "/repo/Patrick.py",
            "oldString": "name = 'Patrick'",
            "newString": "name = 'Alice'",
            "structuredPatch": [
                {"oldStart": 1, "newStart": 1, "lines": ["-Patrick", "+Alice"]}
            ],
        },
    }
    output = await handle_hook(event, pipeline)
    assert output is not None
    updated = output["hookSpecificOutput"]["updatedToolOutput"]
    assert updated["oldString"] == "name = '<<PERSON:1>>'"
    assert updated["structuredPatch"][0]["lines"][0] == "-<<PERSON:1>>"
    assert updated["filePath"] == "/repo/Patrick.py"
    assert updated["structuredPatch"][0]["oldStart"] == 1


async def test_post_tool_use_unknown_tool_is_passthrough() -> None:
    """A structured output from a tool not in the allowlist is passed through."""
    pipeline = _pipeline()
    event = {
        "hook_event_name": "PostToolUse",
        "session_id": "s1",
        "tool_name": "mcp__some__thing",
        "tool_response": {"payload": {"note": "Patrick"}},
    }
    assert await handle_hook(event, pipeline) is None
