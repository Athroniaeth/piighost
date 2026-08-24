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
    if output is not None:
        json.dump(output, sys.stdout)
