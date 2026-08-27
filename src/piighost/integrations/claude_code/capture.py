"""Capture logger for the Claude Code hooks integration.

A log-only entrypoint for discovering the real shapes of tool inputs and outputs
before deciding what to anonymize. It reads one hook event as JSON on stdin,
appends it as one JSON line to the file named by PIIGHOST_HOOK_LOG, and never
mutates the event. Wire it into a scratch settings.json, exercise Claude Code,
then inspect the log to see which fields carry model-facing text and which are
metadata (paths, ids, line numbers) that must be left alone.
"""

import json
import os
import sys

_DEFAULT_LOG = "piighost-hook-capture.jsonl"


def capture() -> None:
    """Append the hook event read on stdin to the capture log, mutating nothing."""
    raw = sys.stdin.read()
    try:
        event = json.loads(raw)
    except ValueError:
        return
    path = os.getenv("PIIGHOST_HOOK_LOG", _DEFAULT_LOG)
    with open(path, "a", encoding="utf-8") as log:
        log.write(json.dumps(event) + "\n")


if __name__ == "__main__":
    capture()
