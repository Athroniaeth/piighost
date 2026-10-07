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


async def test_user_prompt_submit_records_the_prompt_without_a_mutation() -> None:
    """The prompt is anonymized into the thread, but no ignored rewrite is emitted.

    Regression: the hook returned updatedPrompt, a field Claude Code ignores, so
    the prompt reached the model in clear while the output claimed otherwise.
    """
    pipeline = _pipeline()
    event = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "s1",
        "prompt": "I am Patrick",
    }
    assert await handle_hook(event, pipeline) is None
    # The value is recorded in the session thread, so its token is known.
    assert await pipeline.deanonymize("<<PERSON:1>>", "s1") == "Patrick"


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
    event = {"hook_event_name": "PreToolUse", "session_id": "s1"}
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


GREP_CONTENT_RESPONSE = {
    "mode": "content",
    "numFiles": 0,
    "filenames": [],
    "content": "customers.csv:2:1,Patrick,pro",
    "numLines": 1,
}
"""A Grep result in content mode, shaped as Claude Code 2.1.280 returns it."""

GREP_FILES_RESPONSE = {
    "mode": "files_with_matches",
    "filenames": ["/home/Patrick/customers.csv"],
    "numFiles": 1,
}
"""A Grep result in files_with_matches mode, which holds only file paths."""


async def test_post_tool_use_anonymizes_grep_matching_lines() -> None:
    """A Grep result in content mode has its matching lines anonymized."""
    pipeline = _pipeline()
    event = {
        "hook_event_name": "PostToolUse",
        "session_id": "s1",
        "tool_name": "Grep",
        "tool_response": GREP_CONTENT_RESPONSE,
    }
    output = await handle_hook(event, pipeline)
    assert output is not None
    updated = output["hookSpecificOutput"]["updatedToolOutput"]
    assert updated == {
        **GREP_CONTENT_RESPONSE,
        "content": "customers.csv:2:1,<<PERSON:1>>,pro",
    }


async def test_post_tool_use_leaves_grep_file_names_untouched() -> None:
    """A Grep result in files_with_matches mode keeps its paths verbatim."""
    pipeline = _pipeline()
    event = {
        "hook_event_name": "PostToolUse",
        "session_id": "s1",
        "tool_name": "Grep",
        "tool_response": GREP_FILES_RESPONSE,
    }
    output = await handle_hook(event, pipeline)
    assert output is not None
    assert output["hookSpecificOutput"]["updatedToolOutput"] == GREP_FILES_RESPONSE


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

NOTICE = (
    "[piighost could not de-identify this PostToolUse event (ConnectError: All "
    "connection attempts failed), so the tool output is withheld.]"
)
"""The notice that replaces a tool output's text when the server is down."""

NO_SESSION_NOTICE = (
    "[piighost could not de-identify this PostToolUse event (MissingThreadIdError: "
    "The hook event carries no session_id, the thread its values belong to.), so "
    "the tool output is withheld.]"
)
"""The notice that replaces a tool output's text when its event has no session id."""

READ_RESPONSE = {
    "type": "text",
    "file": {
        "filePath": "/repo/.env",
        "content": "PATRICK_KEY=sk_test_FAKE",
        "numLines": 1,
        "startLine": 1,
        "totalLines": 1,
    },
}
"""A Read result, shaped as Claude Code 2.1.280 returns it."""


def _tool_output(
    tool_name: str, tool_response: object, session_id: str | None = "s1"
) -> dict[str, object]:
    """A PostToolUse event for one tool output, without a session id if None."""
    event: dict[str, object] = {
        "hook_event_name": "PostToolUse",
        "tool_name": tool_name,
        "tool_response": tool_response,
    }
    if session_id is not None:
        event["session_id"] = session_id
    return event


WITHHELD_OUTPUTS: dict[str, tuple[dict[str, object], object]] = {
    "a plain string": (_tool_output("Bash", "Patrick ran the build"), NOTICE),
    "a Read result": (
        _tool_output("Read", READ_RESPONSE),
        {**READ_RESPONSE, "file": {**READ_RESPONSE["file"], "content": NOTICE}},
    ),
    "a Grep result": (
        _tool_output("Grep", GREP_CONTENT_RESPONSE),
        {**GREP_CONTENT_RESPONSE, "content": NOTICE},
    ),
    "an MCP tool result without a session id": (
        _tool_output("mcp__crm__lookup", [{"text": "Patrick"}], session_id=None),
        NO_SESSION_NOTICE,
    ),
}
"""Per case, a tool output event and the replacement the runner emits for it.

A built-in tool keeps its shape, since Claude Code ignores any other replacement
for it. An MCP tool's output is not validated, so the notice replaces it whole.
The hook only calls the server for a tool it knows, so an MCP output reaches the
failure path through a missing session id.
"""


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


@pytest.mark.parametrize(
    ("event", "withheld"), WITHHELD_OUTPUTS.values(), ids=WITHHELD_OUTPUTS.keys()
)
def test_the_runner_withholds_a_tool_output_in_its_own_shape(
    event: dict[str, object],
    withheld: object,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A tool output the runner cannot de-identify has its text replaced by a notice.

    Regression: the notice replaced a built-in tool's structured output as a plain
    string, which Claude Code ignored, so a .env reached the model in clear.
    """
    _run(event, monkeypatch)
    replaced = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert replaced["updatedToolOutput"] == withheld


def test_the_runner_warns_on_an_output_it_cannot_withhold(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unlisted built-in tool's output cannot be replaced, so the runner warns.

    It exits with the blocking code, which shows the reason to Claude, and emits
    no replacement Claude Code would reject.
    """
    event = _tool_output("NotebookRead", {"cells": ["Patrick"]}, session_id=None)
    with pytest.raises(SystemExit) as caught:
        _run(event, monkeypatch)
    captured = capsys.readouterr()
    assert caught.value.code == 2
    assert captured.out == ""
    assert "was not withheld" in captured.err
    assert "Patrick" not in captured.err


def test_an_unlisted_tool_output_passes_through_without_the_server(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The hook never calls the server for an unlisted tool, so it passes, even down."""
    _run(_tool_output("mcp__crm__lookup", [{"text": "Patrick"}]), monkeypatch)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


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
