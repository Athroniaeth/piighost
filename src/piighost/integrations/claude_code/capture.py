"""Capture logger for the Claude Code hooks integration.

A log-only entrypoint for discovering the real shapes of tool inputs and outputs
before deciding what to anonymize. It reads one hook event as JSON on stdin,
appends it as one JSON line to the file named by PIIGHOST_HOOK_LOG, and never
mutates the event. Wire it into a scratch settings.json, exercise Claude Code,
then inspect the log to see which fields carry model-facing text and which are
metadata (paths, ids, line numbers) that must be left alone.

The log holds the event in clear text, so it carries the user prompt, the content
of the files that were read or written, and the output of the commands that ran.
It is a development-machine tool: nothing is written unless PIIGHOST_HOOK_LOG
names a file, so a forgotten variable cannot drop a file of clear PII in the
working directory.
"""

import json
import os
import sys


def capture() -> None:
    """Append the hook event read on stdin to the capture log, mutating nothing.

    Without PIIGHOST_HOOK_LOG, or with an empty one, the event is dropped and no
    file is created. stdin is still consumed, so the hook behaves the same way
    for Claude Code either way.
    """
    raw = sys.stdin.read()
    path = os.getenv("PIIGHOST_HOOK_LOG")
    if not path:
        return
    try:
        event = json.loads(raw)
    except ValueError:
        return
    with open(path, "a", encoding="utf-8") as log:
        log.write(json.dumps(event) + "\n")


if __name__ == "__main__":
    capture()
