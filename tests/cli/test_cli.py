"""Tests for the piighost command-line interface."""

import json
from pathlib import Path
from typing import Self

import pytest
from typer.testing import CliRunner

from piighost.cli import DEFAULT_CATALOG, app
from piighost.hub import HubUnreachableError

runner = CliRunner()

_VALID_TOML = """
name = "demo"

[detector]
type = "regex"
patterns = { EMAIL = "[a-z]+@[a-z.]+" }

[linker]
type = "exact"

[anonymizer.placeholder]
type = "redact"
"""


def _write(tmp_path: Path, text: str) -> Path:
    """Write text to a config.toml under tmp_path and return the path."""
    path = tmp_path / "config.toml"
    path.write_text(text)
    return path


class TestConformance:
    def test_app_exposes_its_commands(self) -> None:
        """The app registers the validate, schema, and anonymize commands."""
        names = set()
        for command in app.registered_commands:
            callback = command.callback
            assert callback is not None
            names.add(callback.__name__)
        assert names == {"validate", "schema", "anonymize"}


class TestValidate:
    def test_valid_config_exits_zero(self, tmp_path: Path) -> None:
        """validate on a valid config exits 0 and prints OK."""
        path = _write(tmp_path, _VALID_TOML)
        result = runner.invoke(app, ["validate", str(path)])
        assert result.exit_code == 0
        assert result.output.startswith("OK:")

    def test_invalid_schema_exits_one(self, tmp_path: Path) -> None:
        """validate on a config missing a detector type exits 1 with a message."""
        bad = _VALID_TOML.replace('type = "regex"\n', "")
        path = _write(tmp_path, bad)
        result = runner.invoke(app, ["validate", str(path)])
        assert result.exit_code == 1
        assert "invalid configuration" in result.stderr

    def test_invalid_toml_exits_one(self, tmp_path: Path) -> None:
        """validate on syntactically invalid TOML exits 1."""
        path = _write(tmp_path, "x = = y")
        result = runner.invoke(app, ["validate", str(path)])
        assert result.exit_code == 1
        assert result.stderr

    def test_missing_file_exits_one(self, tmp_path: Path) -> None:
        """validate on an absent file exits 1."""
        result = runner.invoke(app, ["validate", str(tmp_path / "absent.toml")])
        assert result.exit_code == 1
        assert result.stderr


class TestValidateHub:
    def test_a_hub_reference_is_validated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """validate takes a hub reference as it takes a file."""
        monkeypatch.setattr(
            "piighost.config.settings.pull_config", lambda ref: _VALID_TOML
        )
        result = runner.invoke(app, ["validate", "hub:piighost/demo:2f602547"])
        assert result.exit_code == 0
        assert "OK: hub:piighost/demo:2f602547" in result.stdout

    def test_an_unreachable_hub_fails_with_a_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A hub that cannot be reached exits 1 with a line, not a traceback."""

        def pull_config(ref: str) -> str:
            raise HubUnreachableError(f"{ref}: the hub answered 404")

        monkeypatch.setattr("piighost.config.settings.pull_config", pull_config)
        result = runner.invoke(app, ["validate", "hub:piighost/nope:2f602547"])
        assert result.exit_code == 1
        assert "the hub answered 404" in result.stderr


class TestSchema:
    def test_schema_prints_json_with_expected_fields(self) -> None:
        """schema exits 0 and prints a JSON schema covering the components."""
        result = runner.invoke(app, ["schema"])
        assert result.exit_code == 0
        document = json.loads(result.output)
        assert {"detector", "linker", "anonymizer"} <= set(document["properties"])


@pytest.fixture(autouse=True)
def fake_hub(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Answer every hub pull with an email pattern, recording each reference."""
    pulled: list[str] = []

    def pull(ref: str, hub: str | None = None) -> dict[str, str]:
        pulled.append(ref)
        return {"EMAIL": "[a-z]+@[a-z.]+"}

    monkeypatch.setattr("piighost.hub.pull", pull)
    return pulled


class TestAnonymize:
    def test_default_detector_anonymizes_an_argument(self, fake_hub: list[str]) -> None:
        """With no config, the regex detector over the pinned hub group tokenizes."""
        result = runner.invoke(app, ["anonymize", "mail me at a@b.co please"])
        assert result.exit_code == 0
        assert fake_hub == [DEFAULT_CATALOG]
        assert "a@b.co" not in result.stdout
        assert "<<EMAIL:1>>" in result.stdout

    def test_reads_stdin_on_dash(self) -> None:
        """A dash argument reads the text from stdin."""
        result = runner.invoke(app, ["anonymize", "-"], input="write a@b.co here")
        assert result.exit_code == 0
        assert "<<EMAIL:1>>" in result.stdout
        assert "a@b.co" not in result.stdout

    def test_json_output_carries_text_and_detections(self) -> None:
        """--json prints the anonymized text and the detections as JSON."""
        result = runner.invoke(app, ["anonymize", "a@b.co", "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["anonymized_text"] == "<<EMAIL:1>>"
        assert [d["text"] for d in payload["detections"]] == ["a@b.co"]

    def test_an_unreachable_hub_fails_with_a_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A hub that cannot be reached exits 1 with a line, not a traceback."""

        def pull(ref: str, hub: str | None = None) -> dict[str, str]:
            raise HubUnreachableError("no route to hub")

        monkeypatch.setattr("piighost.hub.pull", pull)
        result = runner.invoke(app, ["anonymize", "a@b.co"])
        assert result.exit_code == 1
        assert "Could not pull a hub catalog" in result.stderr

    def test_config_pipeline_is_used(self, tmp_path: Path) -> None:
        """--config anonymizes through the configured pipeline."""
        path = _write(tmp_path, _VALID_TOML)
        result = runner.invoke(
            app, ["anonymize", "reach a@b.co now", "--config", str(path)]
        )
        assert result.exit_code == 0
        assert "a@b.co" not in result.stdout
        assert "<<REDACT>>" in result.stdout

    def test_an_invalid_config_fails_with_a_message(self, tmp_path: Path) -> None:
        """A config that does not validate exits 1 with the reason, no traceback."""
        path = _write(tmp_path, _VALID_TOML.replace("patterns =", "pattern ="))
        result = runner.invoke(app, ["anonymize", "a@b.co", "--config", str(path)])
        assert result.exit_code == 1
        assert "invalid configuration" in result.stderr
        assert result.exception is None or isinstance(result.exception, SystemExit)

    def test_json_lists_the_detections_the_text_replaced(self, tmp_path: Path) -> None:
        """--json reports what the pipeline kept, not the detector's raw overlaps."""
        overlapping = """
[detector]
type = "regex"
patterns = { EMAIL = '[a-z]+@[a-z.]+', DOMAIN = '[a-z]+[.]co' }
"""
        path = _write(tmp_path, overlapping)
        result = runner.invoke(
            app, ["anonymize", "write alice@corp.co", "--config", str(path), "--json"]
        )
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["anonymized_text"] == "write <<EMAIL:1>>"
        assert [d["text"] for d in payload["detections"]] == ["alice@corp.co"]

    def test_config_and_api_are_mutually_exclusive(self) -> None:
        """Passing both --config and --api exits 1 with a message."""
        result = runner.invoke(
            app, ["anonymize", "x", "--config", "c.toml", "--api", "http://api"]
        )
        assert result.exit_code == 1
        assert "at most one" in result.output

    def test_api_uses_the_remote_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """--api routes anonymization through a PIIGhostClient over the given URL."""

        class _FakeResult:
            text = "<<EMAIL:1>>"

        class _FakeClient:
            def __init__(self, url: str) -> None:
                self.url = url

            async def __aenter__(self) -> Self:
                return self

            async def __aexit__(self, *args: object) -> None:
                return None

            async def anonymize(self, text: str, thread_id: str) -> _FakeResult:
                return _FakeResult()

        monkeypatch.setattr("piighost.integrations.client.PIIGhostClient", _FakeClient)
        result = runner.invoke(app, ["anonymize", "a@b.co", "--api", "http://api"])
        assert result.exit_code == 0
        assert "<<EMAIL:1>>" in result.stdout
