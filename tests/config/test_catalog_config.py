"""Tests for loading a whole pipeline configuration from a catalog reference."""

from pathlib import Path

import pytest

from piighost.components.detector import RegexDetector
from piighost.config import load_config, load_pipeline, load_thread_pipeline
from piighost.exceptions import ConfigFileError, ConfigValidationError
from piighost.pipeline import ThreadAnonymizationPipeline

REF = "catalog:piighost/notarial:2f602547"
"""The reference every case loads."""

STATELESS = """name = 'piighost/notarial:2f602547'

[detector]
type = 'regex'
patterns = { EMAIL = '[a-z]+@[a-z.]+' }
"""
"""A catalog configuration with no memory."""

THREAD = (
    STATELESS
    + """
[memory]
type = 'in_memory'
"""
)
"""A catalog configuration declaring an in-process memory."""


@pytest.fixture
def catalog(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Answer pull_config from a mutable table of reference to body."""
    bodies = {REF: STATELESS}
    monkeypatch.setattr("piighost.config.settings.pull_config", bodies.__getitem__)
    return bodies


class TestLoadConfigFromTheCatalog:
    def test_a_reference_loads_the_configuration_it_names(
        self, catalog: dict[str, str]
    ) -> None:
        """A catalog: reference reads like a file holding the same TOML."""
        config = load_config(REF)
        assert config.name == "piighost/notarial:2f602547"
        assert config.detector.build().patterns == {"EMAIL": "[a-z]+@[a-z.]+"}  # type: ignore[union-attr]

    def test_the_environment_still_overrides_the_catalog(
        self, catalog: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A PIIGHOST_ variable beats the catalog, as it beats a file."""
        monkeypatch.setenv("PIIGHOST_NAME", "local")
        assert load_config(REF).name == "local"

    async def test_load_pipeline_builds_and_runs_it(
        self, catalog: dict[str, str]
    ) -> None:
        """load_pipeline takes a reference as it takes a path."""
        pipeline = load_pipeline(REF)
        assert isinstance(pipeline.detector, RegexDetector)
        result = await pipeline.anonymize("write a@b.co")
        assert result.text == "write <<EMAIL:1>>"

    def test_load_thread_pipeline_takes_a_reference(
        self, catalog: dict[str, str]
    ) -> None:
        """A catalog configuration with a memory builds a thread pipeline."""
        catalog[REF] = THREAD
        assert isinstance(load_thread_pipeline(REF), ThreadAnonymizationPipeline)

    def test_a_body_that_is_not_toml_names_the_reference(
        self, catalog: dict[str, str]
    ) -> None:
        """A broken answer is a file error that says which reference it came from."""
        catalog[REF] = "[detector"
        with pytest.raises(ConfigFileError, match=REF):
            load_config(REF)

    def test_an_invalid_configuration_names_the_reference(
        self, catalog: dict[str, str]
    ) -> None:
        """A schema error says which reference failed, as it says which file."""
        catalog[REF] = STATELESS.replace("patterns", "pattern")
        with pytest.raises(ConfigValidationError, match=REF):
            load_config(REF)

    def test_a_path_is_still_a_path(self, tmp_path: Path) -> None:
        """A file whose name has no catalog: prefix is read from disk."""
        path = tmp_path / "catalog.toml"
        path.write_text(STATELESS)
        assert load_config(path).name == "piighost/notarial:2f602547"

    def test_a_1x_hub_reference_still_loads(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A source written hub:namespace/name, as 1.x did, is pulled like catalog:."""
        legacy = REF.replace("catalog:", "hub:", 1)
        monkeypatch.setattr(
            "piighost.config.settings.pull_config", {legacy: STATELESS}.__getitem__
        )
        assert load_config(legacy).name == "piighost/notarial:2f602547"
        assert isinstance(load_pipeline(legacy).detector, RegexDetector)
