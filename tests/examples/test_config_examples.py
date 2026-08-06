"""The example config files stay loadable as the config code evolves."""

from pathlib import Path

import pytest

from piighost.config import load_client, load_config

_CONFIG_DIR = Path(__file__).resolve().parents[2] / "examples" / "config"

_PIPELINE_CONFIGS = [
    "minimal.toml",
    "minimal.json",
    "pipeline.toml",
    "thread_redis.toml",
]


@pytest.mark.parametrize("name", _PIPELINE_CONFIGS)
def test_example_pipeline_config_parses(name: str) -> None:
    """Every example pipeline config parses into a valid PipelineConfig."""
    load_config(_CONFIG_DIR / name)


def test_example_client_config_builds() -> None:
    """The remote client example config builds a PIIGhostClient."""
    load_client(_CONFIG_DIR / "remote_client.toml")
