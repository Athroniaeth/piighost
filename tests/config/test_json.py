"""Tests for loading a config from a JSON file."""

import json
from pathlib import Path

import pytest

from piighost.config import load_config, load_pipeline
from piighost.exceptions import ConfigFileError, ConfigValidationError

_CONFIG = {
    "detector": {"type": "regex", "patterns": {"EMAIL": "[a-z]+@[a-z.]+"}},
    "linker": {"type": "exact"},
    "anonymizer": {"placeholder": {"type": "redact"}},
}


def _write_json(tmp_path: Path, data: dict[str, object]) -> Path:
    """Write data as JSON to a config.json under tmp_path and return the path."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data))
    return path


class TestLoadJson:
    def test_valid_json_parses(self, tmp_path: Path) -> None:
        """A valid JSON file parses into a PipelineConfig."""
        config = load_config(_write_json(tmp_path, _CONFIG))
        assert config.detector.type == "regex"

    async def test_json_builds_a_working_pipeline(self, tmp_path: Path) -> None:
        """load_pipeline on a JSON file anonymizes end to end."""
        pipeline = load_pipeline(_write_json(tmp_path, _CONFIG))
        result = await pipeline.anonymize("reach a@b.co now")
        assert result.text == "reach <<REDACT>> now"

    def test_invalid_json_raises_config_file_error(self, tmp_path: Path) -> None:
        """A syntactically invalid JSON file raises ConfigFileError."""
        path = tmp_path / "config.json"
        path.write_text("{ not valid json")
        with pytest.raises(ConfigFileError):
            load_config(path)

    def test_invalid_schema_raises_config_validation_error(
        self, tmp_path: Path
    ) -> None:
        """A valid JSON whose detector has no type raises ConfigValidationError."""
        bad = {**_CONFIG, "detector": {"patterns": {"EMAIL": "[a-z]+@[a-z.]+"}}}
        with pytest.raises(ConfigValidationError):
            load_config(_write_json(tmp_path, bad))
