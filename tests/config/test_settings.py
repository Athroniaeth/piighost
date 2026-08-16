"""Tests for loading a pipeline config from TOML via pydantic-settings."""

import os
import re
from pathlib import Path

import pytest

from piighost.components.entity_resolver import MergeEntityResolver
from piighost.components.expander import WordBoundaryExpander
from piighost.components.overlap_resolver import ConfidenceOverlapResolver
from piighost.components.override import DetectionOverride
from piighost.config import PipelineConfig, load_config, load_pipeline
from piighost.exceptions import (
    ConfigFileError,
    ConfigValidationError,
    PIIRemainingError,
)

_VALID_TOML = """
name = "from-file"

[detector]
type = "regex"
patterns = { EMAIL = "[a-z]+@[a-z.]+" }

[linker]
type = "exact"

[anonymizer.placeholder]
type = "redact"
"""
"""A minimal valid pipeline config, reused as the base for the load cases."""


def _write(tmp_path: Path, text: str) -> Path:
    """Write text to a config.toml under tmp_path and return the path."""
    path = tmp_path / "config.toml"
    path.write_text(text)
    return path


class TestLoadConfig:
    def test_valid_toml_parses(self, tmp_path: Path) -> None:
        """A valid TOML parses into a PipelineConfig."""
        config = load_config(_write(tmp_path, _VALID_TOML))
        assert isinstance(config, PipelineConfig)
        assert config.name == "from-file"

    def test_missing_file_raises_config_file_error(self, tmp_path: Path) -> None:
        """A missing file raises ConfigFileError."""
        with pytest.raises(ConfigFileError):
            load_config(tmp_path / "absent.toml")

    def test_invalid_toml_raises_config_file_error(self, tmp_path: Path) -> None:
        """Syntactically invalid TOML raises ConfigFileError."""
        with pytest.raises(ConfigFileError):
            load_config(_write(tmp_path, "this is = = not toml"))

    def test_invalid_schema_raises_config_validation_error(
        self, tmp_path: Path
    ) -> None:
        """A detector without a type raises ConfigValidationError."""
        bad = _VALID_TOML.replace('type = "regex"\n', "")
        with pytest.raises(ConfigValidationError):
            load_config(_write(tmp_path, bad))

    def test_uncompilable_regex_raises_config_validation_error(
        self, tmp_path: Path
    ) -> None:
        """A malformed regex pattern fails at load time, not at detection time."""
        bad = _VALID_TOML.replace('EMAIL = "[a-z]+@[a-z.]+"', 'EMAIL = "[a"')
        with pytest.raises(ConfigValidationError):
            load_config(_write(tmp_path, bad))

    def test_unreadable_file_raises_config_file_error(self, tmp_path: Path) -> None:
        """An existing but unreadable file raises ConfigFileError, not OSError."""
        if os.geteuid() == 0:
            pytest.skip("root bypasses file permissions")
        path = _write(tmp_path, _VALID_TOML)
        path.chmod(0)
        try:
            with pytest.raises(ConfigFileError):
                load_config(path)
        finally:
            path.chmod(0o644)

    def test_context_var_does_not_leak_between_loads(self, tmp_path: Path) -> None:
        """Each load reads its own file, the path does not leak across calls."""
        first = load_config(_write(tmp_path, _VALID_TOML))
        assert first.name == "from-file"
        other = tmp_path / "other.toml"
        other.write_text(_VALID_TOML.replace('name = "from-file"', 'name = "other"'))
        second = load_config(other)
        assert second.name == "other"


class TestEnvOverride:
    def test_env_overrides_a_top_level_scalar(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A PIIGHOST_ env var overrides the file's top-level scalar."""
        monkeypatch.setenv("PIIGHOST_NAME", "from-env")
        config = load_config(_write(tmp_path, _VALID_TOML))
        assert config.name == "from-env"


class TestLoadPipeline:
    async def test_builds_a_working_pipeline(self, tmp_path: Path) -> None:
        """load_pipeline builds a pipeline that anonymizes end to end."""
        pipeline = load_pipeline(_write(tmp_path, _VALID_TOML))
        result = await pipeline.anonymize("reach a@b.co now")
        assert result.text == "reach <<REDACT>> now"

    async def test_composite_detector_from_toml(self, tmp_path: Path) -> None:
        """A composite detector declared in TOML builds and runs."""
        toml = _VALID_TOML.replace(
            '[detector]\ntype = "regex"\npatterns = { EMAIL = "[a-z]+@[a-z.]+" }\n',
            '[detector]\ntype = "composite"\n'
            '[[detector.detectors]]\ntype = "regex"\npatterns = { EMAIL = "[a-z]+@[a-z.]+" }\n',
        )
        pipeline = load_pipeline(_write(tmp_path, toml))
        result = await pipeline.anonymize("reach a@b.co now")
        assert result.text == "reach <<REDACT>> now"


_STAGES_TOML = """
[detector]
type = "regex"
patterns = { EMAIL = "[a-z]+@[a-z.]+" }

[linker]
type = "exact"

[anonymizer.placeholder]
type = "redact"

[overlap_resolver]
type = "confidence"

[expander]
type = "word_boundary"
case_sensitive = true

[entity_resolver]
type = "merge"

[override.whitelist]
type = "regex"
patterns = { CODE = "banana" }
"""
"""A config enabling every optional stage, for the wiring and override cases."""


class TestOptionalStagesWiring:
    def test_pipeline_wires_every_configured_stage(self, tmp_path: Path) -> None:
        """load_pipeline wires each configured optional stage into the pipeline."""
        pipeline = load_pipeline(_write(tmp_path, _STAGES_TOML))
        assert isinstance(pipeline.overlap_resolver, ConfidenceOverlapResolver)
        assert isinstance(pipeline.expander, WordBoundaryExpander)
        assert pipeline.expander.case_sensitive is True
        assert isinstance(pipeline.entity_resolver, MergeEntityResolver)
        assert isinstance(pipeline.override, DetectionOverride)

    def test_omitted_stages_are_none(self, tmp_path: Path) -> None:
        """A config without a stage leaves that pipeline stage disabled."""
        pipeline = load_pipeline(_write(tmp_path, _VALID_TOML))
        assert pipeline.overlap_resolver is None
        assert pipeline.expander is None
        assert pipeline.entity_resolver is None
        assert pipeline.guard is None
        assert pipeline.override is None


class TestOverrideEffect:
    async def test_whitelist_forces_a_detection(self, tmp_path: Path) -> None:
        """A whitelist detector forces anonymization of a value the detector missed."""
        pipeline = load_pipeline(_write(tmp_path, _STAGES_TOML))
        result = await pipeline.anonymize("mail a@b.co about banana")
        assert "banana" not in result.text
        assert "a@b.co" not in result.text


class TestGuardEffect:
    async def test_detector_guard_raises_on_residual(self, tmp_path: Path) -> None:
        """A detector guard raises PIIRemainingError on residual clear PII."""
        toml = """
[detector]
type = "regex"
patterns = { EMAIL = "[a-z]+@[a-z.]+" }

[linker]
type = "exact"

[anonymizer.placeholder]
type = "redact"

[guard]
type = "detector"

[guard.detector]
type = "regex"
patterns = { WORD = "banana" }
"""
        pipeline = load_pipeline(_write(tmp_path, toml))
        with pytest.raises(PIIRemainingError):
            await pipeline.anonymize("mail a@b.co about banana")


class TestHashFactoryEndToEnd:
    async def test_label_hash_renders_a_hashed_token(self, tmp_path: Path) -> None:
        """A label_hash anonymizer renders a hashed token for a detection."""
        toml = _VALID_TOML.replace('type = "redact"', 'type = "label_hash"')
        pipeline = load_pipeline(_write(tmp_path, toml))
        result = await pipeline.anonymize("mail a@b.co now")
        assert re.search(r"<<EMAIL:[0-9a-f]{8}>>", result.text)


class TestObservationRedactorWiring:
    def test_observation_redactor_is_wired(self, tmp_path: Path) -> None:
        """An observation_redactor placeholder config wires into the pipeline."""
        toml = _VALID_TOML + '\n[observation_redactor]\ntype = "label"\n'
        pipeline = load_pipeline(_write(tmp_path, toml))
        assert pipeline.observation_redactor is not None
