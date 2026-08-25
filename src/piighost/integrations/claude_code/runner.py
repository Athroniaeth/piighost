"""Runner entrypoint for the Claude Code hooks integration (optional: client).

Reads one hook event as JSON on stdin, anonymizes or restores through a remote
PIIGhostClient keyed by the session id, and writes the mutation as JSON on stdout.
Wire it into a Claude Code settings.json, see settings.template.json. The server
base URL comes from PIIGHOST_API_URL, defaulting to a local piighost-api.
"""

import asyncio
import json
import os
import sys
from typing import Any

from piighost.integrations.claude_code.hooks import handle_hook
from piighost.integrations.client import PIIGhostClient

_DEFAULT_API_URL = "http://localhost:8000"


def _debug_record(
    event: dict[str, Any], output: dict[str, Any] | None
) -> dict[str, Any]:
    """A compact record of one hook invocation for the optional debug log."""
    return {
        "event": event.get("hook_event_name"),
        "tool": event.get("tool_name"),
        "session_id": event.get("session_id"),
        "output": output,
    }


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

    output = asyncio.run(_handle())
    _log(event, output)
    if output is not None:
        json.dump(output, sys.stdout)
