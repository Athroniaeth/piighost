"""Tests for loading a whole pipeline configuration from a hub reference."""

from pathlib import Path

import pytest

from piighost.components.detector import RegexDetector
from piighost.config import load_config, load_pipeline, load_thread_pipeline
from piighost.exceptions import ConfigFileError, ConfigValidationError
from piighost.pipeline import ThreadAnonymizationPipeline

REF = "hub:piighost/notarial:2f602547"
"""The reference every case loads."""

STATELESS = """name = 'piighost/notarial:2f602547'

[detector]
type = 'regex'
patterns = { EMAIL = '[a-z]+@[a-z.]+' }
"""
"""A hub configuration with no memory."""

THREAD = (
    STATELESS
    + """
[memory]
type = 'in_memory'
"""
)
"""A hub configuration declaring an in-process memory."""


@pytest.fixture
def hub(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Answer pull_config from a mutable table of reference to body."""
    bodies = {REF: STATELESS}
    monkeypatch.setattr("piighost.config.settings.pull_config", bodies.__getitem__)
    return bodies


class TestLoadConfigFromTheHub:
    def test_a_reference_loads_the_configuration_it_names(
        self, hub: dict[str, str]
    ) -> None:
        """A hub: reference reads like a file holding the same TOML."""
        config = load_config(REF)
        assert config.name == "piighost/notarial:2f602547"
        assert config.detector.build().patterns == {"EMAIL": "[a-z]+@[a-z.]+"}  # type: ignore[union-attr]

    def test_the_environment_still_overrides_the_hub(
        self, hub: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A PIIGHOST_ variable beats the hub, as it beats a file."""
        monkeypatch.setenv("PIIGHOST_NAME", "local")
        assert load_config(REF).name == "local"

    async def test_load_pipeline_builds_and_runs_it(self, hub: dict[str, str]) -> None:
        """load_pipeline takes a reference as it takes a path."""
        pipeline = load_pipeline(REF)
        assert isinstance(pipeline.detector, RegexDetector)
        result = await pipeline.anonymize("write a@b.co")
        assert result.text == "write <<EMAIL:1>>"

    def test_load_thread_pipeline_takes_a_reference(self, hub: dict[str, str]) -> None:
        """A hub configuration with a memory builds a thread pipeline."""
        hub[REF] = THREAD
        assert isinstance(load_thread_pipeline(REF), ThreadAnonymizationPipeline)

    def test_a_body_that_is_not_toml_names_the_reference(
        self, hub: dict[str, str]
    ) -> None:
        """A broken answer is a file error that says which reference it came from."""
        hub[REF] = "[detector"
        with pytest.raises(ConfigFileError, match=REF):
            load_config(REF)

    def test_an_invalid_configuration_names_the_reference(
        self, hub: dict[str, str]
    ) -> None:
        """A schema error says which reference failed, as it says which file."""
        hub[REF] = STATELESS.replace("patterns", "pattern")
        with pytest.raises(ConfigValidationError, match=REF):
            load_config(REF)

    def test_a_path_is_still_a_path(self, tmp_path: Path) -> None:
        """A file whose name has no hub: prefix is read from disk."""
        path = tmp_path / "hub.toml"
        path.write_text(STATELESS)
        assert load_config(path).name == "piighost/notarial:2f602547"
