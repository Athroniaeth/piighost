"""Runner entrypoint for the Claude Code hooks integration (optional: client).

Reads one hook event as JSON on stdin, anonymizes or restores through a remote
PIIGhostClient keyed by the session id, and writes the mutation as JSON on stdout.
Wire it into a Claude Code settings.json, see settings.template.json. The server
base URL comes from PIIGHOST_API_URL, defaulting to a local piighost-api.

A hook that cannot de-identify fails closed: the prompt or the tool call is
blocked and a tool output is withheld, so an unreachable server never lets text
through in clear. PIIGHOST_HOOK_FAIL_OPEN=1 lets the text through instead.
"""

import asyncio
import json
import os
import sys
from typing import Any

from piighost.integrations.claude_code.hooks import _output, handle_hook
from piighost.integrations.client import PIIGhostClient

_DEFAULT_API_URL = "http://localhost:8000"

FAIL_OPEN_ENV_VAR = "PIIGHOST_HOOK_FAIL_OPEN"
"""Set to 1 to let text through in clear when a hook cannot de-identify it."""

_BLOCKING_EXIT_CODE = 2
"""The exit code Claude Code reads as a block, for a prompt or a tool call.

Any other non-zero code is a non-blocking error after which the text goes on.
A tool output cannot be blocked this way, since the tool already ran, so it is
replaced instead.
"""


def _debug_record(
    event: dict[str, Any], output: dict[str, Any] | None
) -> dict[str, Any]:
    """A compact record of one hook invocation for the optional debug log.

    A tool output the hooks passed through is logged whole, so the shape of a
    tool missing from the allowlist can be read and its text fields added.
    """
    record = {
        "event": event.get("hook_event_name"),
        "tool": event.get("tool_name"),
        "session_id": event.get("session_id"),
        "output": output,
    }
    if output is None and "tool_response" in event:
        record["tool_response"] = event["tool_response"]
    return record


def _log(event: dict[str, Any], output: dict[str, Any] | None) -> None:
    """Append a debug record to PIIGHOST_HOOK_LOG when it is set, else do nothing.

    Handy to watch what the hooks anonymize during a live test. The record can
    contain restored real values (for a PreToolUse input), so keep the log local.
    """
    path = os.getenv("PIIGHOST_HOOK_LOG")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as log:
        log.write(json.dumps(_debug_record(event, output)) + "\n")


def _fail(event: dict[str, Any], error: Exception) -> dict[str, Any] | None:
    """Fail closed on a hook that could not de-identify, or open if asked to.

    A tool output is replaced by a notice. A prompt or a tool call is blocked by
    exiting with the blocking code, the reason on stderr. Only the error is named,
    never the text.
    """
    name = event.get("hook_event_name")
    reason = f"piighost could not de-identify this {name} event ({type(error).__name__}: {error})"
    if os.getenv(FAIL_OPEN_ENV_VAR) == "1":
        print(
            f"{reason}; {FAIL_OPEN_ENV_VAR}=1, so it goes on in clear.", file=sys.stderr
        )
        return None
    if name == "PostToolUse":
        return _output(
            name, {"updatedToolOutput": f"[{reason}, so the tool output is withheld.]"}
        )
    print(f"{reason}, so it is blocked.", file=sys.stderr)
    sys.exit(_BLOCKING_EXIT_CODE)


def run() -> None:
    """Read a hook event on stdin and emit its mutation on stdout, if any."""
    raw = sys.stdin.read()
    try:
        event = json.loads(raw)
    except ValueError:
        return
    if not isinstance(event, dict):
        return
    base_url = os.getenv("PIIGHOST_API_URL", _DEFAULT_API_URL)

    async def _handle() -> dict[str, Any] | None:
        async with PIIGhostClient(base_url) as client:
            return await handle_hook(event, client)

    try:
        output = asyncio.run(_handle())
    except Exception as error:  # noqa: BLE001, any failure leaves the text unprotected
        output = _fail(event, error)
    _log(event, output)
    if output is not None:
        json.dump(output, sys.stdout)
