import json
from pathlib import Path

from typer.testing import CliRunner

from piighost.cli import app

runner = CliRunner()
FIXTURES = Path(__file__).parent.parent / "config" / "fixtures"


def test_validate_succeeds_on_minimal_toml():
    result = runner.invoke(app, ["validate", str(FIXTURES / "minimal.toml")])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output


def test_validate_fails_on_unknown_key():
    result = runner.invoke(
        app, ["validate", str(FIXTURES / "invalid" / "unknown_key.toml")]
    )
    assert result.exit_code == 1
    assert "rogue_key" in result.output


def test_validate_fails_on_missing_file():
    result = runner.invoke(app, ["validate", "/tmp/no_such_file_xyz.toml"])
    assert result.exit_code == 1


def test_schema_outputs_valid_json():
    result = runner.invoke(app, ["schema"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert "properties" in parsed
    assert "detectors" in parsed["properties"]
