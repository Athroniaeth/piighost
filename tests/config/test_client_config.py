"""Tests for the remote client config."""

from pathlib import Path

from piighost.components.placeholder.label_counter import (
    LabelCounterPlaceholderFactory,
)
from piighost.config import load_client
from piighost.config.settings import ClientConfig
from piighost.integrations.client import PIIGhostClient
from piighost.pipeline import AnyThreadPipeline

_BASE_URL = "http://localhost:8000"


class TestClientConfig:
    def test_builds_a_client(self) -> None:
        """The client config builds a PIIGhostClient over its base URL."""
        client = ClientConfig(base_url=_BASE_URL).build()
        assert isinstance(client, PIIGhostClient)

    def test_recognizer_defaults_to_label_counter(self) -> None:
        """The built client's recognizer is the standard label-counter grammar."""
        client = ClientConfig(base_url=_BASE_URL).build()
        assert isinstance(client.recognizer, LabelCounterPlaceholderFactory)

    def test_conforms_to_the_thread_pipeline_port(self) -> None:
        """A built client satisfies the AnyThreadPipeline port."""
        client = ClientConfig(base_url=_BASE_URL).build()
        assert isinstance(client, AnyThreadPipeline)


class TestLoadClient:
    def test_loads_from_toml(self, tmp_path: Path) -> None:
        """load_client builds a PIIGhostClient from a TOML file."""
        path = tmp_path / "client.toml"
        path.write_text('base_url = "http://localhost:8000"\n')
        assert isinstance(load_client(path), PIIGhostClient)

    def test_loads_from_json(self, tmp_path: Path) -> None:
        """load_client builds a PIIGhostClient from a JSON file."""
        path = tmp_path / "client.json"
        path.write_text('{"base_url": "http://localhost:8000"}')
        assert isinstance(load_client(path), PIIGhostClient)
