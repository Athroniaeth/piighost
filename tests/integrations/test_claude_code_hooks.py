"""Tests for the Claude Code hooks integration, over a local thread pipeline.

handle_hook takes any AnyThreadPipeline, so these drive it with a real local
ThreadAnonymizationPipeline and an ExactMatchDetector, no server or httpx needed.
"""

from piighost.components.detector import ExactMatchDetector
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


async def test_missing_field_is_a_no_op() -> None:
    """A malformed event missing its payload field returns no mutation, not an error."""
    pipeline = _pipeline()
    event = {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    assert await handle_hook(event, pipeline) is None


async def test_non_string_tool_output_is_a_no_op() -> None:
    """A structured tool output is passed through untouched for now."""
    pipeline = _pipeline()
    event = {
        "hook_event_name": "PostToolUse",
        "session_id": "s1",
        "tool_name": "Read",
        "tool_response": {"file": {"content": "Patrick"}},
    }
    assert await handle_hook(event, pipeline) is None
