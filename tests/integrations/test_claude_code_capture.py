"""Tests for the Claude Code hook capture logger.

The capture log holds clear text, so the module only writes when
PIIGHOST_HOOK_LOG names a file. These drive capture() over a fake stdin and a
temporary directory, asserting both that an explicit path is honoured and that
no path leaves the directory untouched.
"""

import io
import json
from pathlib import Path

import pytest

from piighost.integrations.claude_code.capture import capture

_EVENT: dict[str, object] = {
    "hook_event_name": "PostToolUse",
    "tool_response": {"file": {"a": 1}},
}
"""A minimal hook event, enough to tell a written line from an empty log."""

_SILENT_SETTINGS: dict[str, str | None] = {
    "unset": None,
    "empty": "",
}
"""PIIGHOST_HOOK_LOG values that must produce no file at all."""


def _feed_event(monkeypatch: pytest.MonkeyPatch) -> None:
    """Put the sample event on stdin, as a hook invocation would."""
    payload = json.dumps(_EVENT)
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))


class TestWithAnExplicitPath:
    def test_appends_the_event_as_jsonl(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The capture logger appends the raw event as one JSON line, mutating nothing."""
        log = tmp_path / "cap.jsonl"
        monkeypatch.setenv("PIIGHOST_HOOK_LOG", str(log))
        _feed_event(monkeypatch)
        capture()
        lines = log.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["tool_response"] == {"file": {"a": 1}}

    def test_appends_rather_than_truncates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A second event is appended below the first, not written over it."""
        log = tmp_path / "cap.jsonl"
        monkeypatch.setenv("PIIGHOST_HOOK_LOG", str(log))
        _feed_event(monkeypatch)
        capture()
        _feed_event(monkeypatch)
        capture()
        assert len(log.read_text(encoding="utf-8").splitlines()) == 2


class TestWithoutAnExplicitPath:
    @pytest.mark.parametrize(("name", "value"), _SILENT_SETTINGS.items())
    def test_writes_no_file_at_all(
        self,
        name: str,
        value: str | None,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Without a log path the event is dropped and no file is created."""
        monkeypatch.chdir(tmp_path)
        if value is None:
            monkeypatch.delenv("PIIGHOST_HOOK_LOG", raising=False)
        else:
            monkeypatch.setenv("PIIGHOST_HOOK_LOG", value)
        _feed_event(monkeypatch)
        capture()
        assert list(tmp_path.iterdir()) == []
