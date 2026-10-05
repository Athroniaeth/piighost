"""Tests for the Claude Code hooks integration, over a local thread pipeline.

handle_hook takes any AnyThreadPipeline, so these drive it with a real local
ThreadAnonymizationPipeline and an ExactMatchDetector, no server needed. The
runner tests point it at a server nothing listens on, to check it fails closed.
"""

import io
import json
from collections.abc import Mapping

import pytest

from piighost.components.detector import ExactMatchDetector
from piighost.exceptions import MissingThreadIdError
from piighost.integrations.claude_code import handle_hook
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


async def test_an_event_without_a_session_id_is_refused() -> None:
    """Without a session id, the hook raises rather than use a shared thread."""
    pipeline = _pipeline()
    event = {"hook_event_name": "UserPromptSubmit", "prompt": "I am Patrick"}
    with pytest.raises(MissingThreadIdError):
        await handle_hook(event, pipeline)


async def test_missing_field_is_a_no_op() -> None:
    """A malformed event missing its payload field returns no mutation, not an error."""
    pipeline = _pipeline()
    event = {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    assert await handle_hook(event, pipeline) is None


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
            "oldString": 'name = "Patrick"',
            "newString": 'name = "Alice"',
            "structuredPatch": [
                {
                    "oldStart": 1,
                    "newStart": 1,
                    "lines": ['-name = "Patrick"', '+name = "Alice"'],
                }
            ],
        },
    }
    output = await handle_hook(event, pipeline)
    assert output is not None
    updated = output["hookSpecificOutput"]["updatedToolOutput"]
    assert updated["oldString"] == 'name = "<<PERSON:1>>"'
    assert updated["structuredPatch"][0]["lines"][0] == '-name = "<<PERSON:1>>"'
    assert updated["filePath"] == "/repo/Patrick.py"
    assert updated["structuredPatch"][0]["oldStart"] == 1


def test_debug_record_is_compact() -> None:
    """The optional debug record keeps the event name, tool, session, and output."""
    from piighost.integrations.claude_code.runner import _debug_record

    record = _debug_record(
        {"hook_event_name": "PostToolUse", "tool_name": "Bash", "session_id": "s1"},
        {"hookSpecificOutput": {"hookEventName": "PostToolUse"}},
    )
    assert record == {
        "event": "PostToolUse",
        "tool": "Bash",
        "session_id": "s1",
        "output": {"hookSpecificOutput": {"hookEventName": "PostToolUse"}},
    }


def test_debug_record_keeps_a_passed_through_tool_output() -> None:
    """An output the hooks left alone is logged whole, to learn the tool's shape."""
    from piighost.integrations.claude_code.runner import _debug_record

    event = {"hook_event_name": "PostToolUse", "tool_response": {"rows": ["x"]}}
    assert _debug_record(event, None)["tool_response"] == {"rows": ["x"]}


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


UNREACHABLE_API_URL = "http://127.0.0.1:9"
"""A server URL nothing listens on, so every runner call fails to connect."""

BLOCKED_EVENTS = {
    "a prompt": {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "s1",
        "prompt": "I am Patrick",
    },
    "a tool call": {
        "hook_event_name": "PreToolUse",
        "session_id": "s1",
        "tool_name": "Bash",
        "tool_input": {"command": "echo <<PERSON:1>>"},
    },
    "a prompt without a session id": {
        "hook_event_name": "UserPromptSubmit",
        "prompt": "I am Patrick",
    },
}
"""Events the runner blocks when it cannot de-identify them."""

TOOL_OUTPUT_EVENT = {
    "hook_event_name": "PostToolUse",
    "session_id": "s1",
    "tool_name": "Bash",
    "tool_response": "Patrick ran the build",
}
"""A tool output, which cannot be blocked since the tool already ran."""


def _run(event: Mapping[str, object], monkeypatch: pytest.MonkeyPatch) -> None:
    """Feed one event to the runner on stdin, against an unreachable server."""
    from piighost.integrations.claude_code.runner import run

    monkeypatch.setenv("PIIGHOST_API_URL", UNREACHABLE_API_URL)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(event)))
    run()


@pytest.mark.parametrize("event", BLOCKED_EVENTS.values(), ids=BLOCKED_EVENTS.keys())
def test_the_runner_blocks_what_it_cannot_de_identify(
    event: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A failed hook exits with the blocking code and names the reason on stderr.

    Regression: it used to crash with code 1, which Claude Code reads as a
    non-blocking error, so the prompt went on in clear (DPO-9).
    """
    with pytest.raises(SystemExit) as caught:
        _run(event, monkeypatch)
    captured = capsys.readouterr()
    assert caught.value.code == 2
    assert captured.out == ""
    assert "so it is blocked" in captured.err
    assert "Patrick" not in captured.err


def test_the_runner_withholds_a_tool_output_it_cannot_de_identify(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A tool output that could not be de-identified is replaced by a notice."""
    _run(TOOL_OUTPUT_EVENT, monkeypatch)
    replaced = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert "withheld" in replaced["updatedToolOutput"]
    assert "Patrick" not in replaced["updatedToolOutput"]


@pytest.mark.parametrize(
    "event",
    [*BLOCKED_EVENTS.values(), TOOL_OUTPUT_EVENT],
    ids=[*BLOCKED_EVENTS.keys(), "a tool output"],
)
def test_fail_open_lets_the_text_through(
    event: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """With PIIGHOST_HOOK_FAIL_OPEN=1, a failed hook mutates nothing and says so."""
    monkeypatch.setenv("PIIGHOST_HOOK_FAIL_OPEN", "1")
    _run(event, monkeypatch)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "goes on in clear" in captured.err
