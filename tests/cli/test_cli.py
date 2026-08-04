"""Tests for the piighost command-line interface."""

import json
from pathlib import Path

from typer.testing import CliRunner

from piighost.cli import app

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
    def test_app_exposes_the_two_commands(self) -> None:
        """The app registers exactly the validate and schema commands."""
        names = {command.callback.__name__ for command in app.registered_commands}
        assert names == {"validate", "schema"}


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
        result = runner.invoke(app, ["validate", str(_write(tmp_path, bad))])
        assert result.exit_code == 1
        assert "invalid configuration" in result.stderr

    def test_invalid_toml_exits_one(self, tmp_path: Path) -> None:
        """validate on syntactically invalid TOML exits 1."""
        result = runner.invoke(app, ["validate", str(_write(tmp_path, "x = = y"))])
        assert result.exit_code == 1
        assert result.stderr

    def test_missing_file_exits_one(self, tmp_path: Path) -> None:
        """validate on an absent file exits 1."""
        result = runner.invoke(app, ["validate", str(tmp_path / "absent.toml")])
        assert result.exit_code == 1
        assert result.stderr


class TestSchema:
    def test_schema_prints_json_with_expected_fields(self) -> None:
        """schema exits 0 and prints a JSON schema covering the components."""
        result = runner.invoke(app, ["schema"])
        assert result.exit_code == 0
        document = json.loads(result.output)
        assert {"detector", "linker", "anonymizer"} <= set(document["properties"])
