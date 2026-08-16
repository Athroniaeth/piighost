"""Tests for building a thread pipeline from config."""

from pathlib import Path

import pytest

from piighost.config import load_pipeline, load_thread_pipeline
from piighost.config.models.memory import InMemoryConfig
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.exceptions import ConfigError
from piighost.pipeline import AnonymizationPipeline, ThreadAnonymizationPipeline

_THREAD_TOML = """
[detector]
type = "exact"
values = { Patrick = "PERSON", Emma = "PERSON" }

[linker]
type = "exact"

[anonymizer.placeholder]
type = "label_counter"

[memory]
type = "in_memory"
"""
"""A thread-pipeline config with two people and an in-memory backend."""

_SIMPLE_TOML = """
[detector]
type = "exact"
values = { Patrick = "PERSON" }

[linker]
type = "exact"

[anonymizer.placeholder]
type = "label_counter"
"""
"""A pipeline config with no memory section, the memory-less counterpart."""


def _write(tmp_path: Path, text: str) -> Path:
    """Write text to a config.toml under tmp_path and return the path."""
    path = tmp_path / "config.toml"
    path.write_text(text)
    return path


class TestInMemoryConfig:
    def test_builds_an_in_memory_backend(self) -> None:
        """The in_memory config builds an InMemoryConversationMemory."""
        memory = InMemoryConfig(type="in_memory").build()
        assert isinstance(memory, InMemoryConversationMemory)


class TestLoadThreadPipeline:
    def test_builds_a_thread_pipeline(self, tmp_path: Path) -> None:
        """load_thread_pipeline builds a ThreadAnonymizationPipeline."""
        pipeline = load_thread_pipeline(_write(tmp_path, _THREAD_TOML))
        assert isinstance(pipeline, ThreadAnonymizationPipeline)

    async def test_memory_shares_placeholder_across_messages(
        self, tmp_path: Path
    ) -> None:
        """A thread keeps an entity's ordinal across messages via its memory.

        Emma is the second person in message one, so a stateless pipeline would
        render it as PERSON:1 in message two; keeping PERSON:2 proves the token
        numbering is shared thread-wide, not recomputed per message.
        """
        pipeline = load_thread_pipeline(_write(tmp_path, _THREAD_TOML))
        first = await pipeline.anonymize("hi Patrick and Emma", "t")
        second = await pipeline.anonymize("bye Emma", "t")
        assert "<<PERSON:1>>" in first.text
        assert "<<PERSON:2>>" in first.text
        assert "<<PERSON:2>>" in second.text

    async def test_threads_are_isolated(self, tmp_path: Path) -> None:
        """A second thread numbers its entities fresh, not inheriting the first."""
        pipeline = load_thread_pipeline(_write(tmp_path, _THREAD_TOML))
        await pipeline.anonymize("hi Patrick and Emma", "a")
        other = await pipeline.anonymize("hi Emma", "b")
        assert "<<PERSON:1>>" in other.text

    def test_missing_memory_is_rejected(self, tmp_path: Path) -> None:
        """load_thread_pipeline on a config without memory raises ConfigError."""
        with pytest.raises(ConfigError):
            load_thread_pipeline(_write(tmp_path, _SIMPLE_TOML))


class TestLoadPipelineRejectsMemory:
    def test_memory_config_is_rejected(self, tmp_path: Path) -> None:
        """load_pipeline on a config declaring a memory raises ConfigError."""
        with pytest.raises(ConfigError):
            load_pipeline(_write(tmp_path, _THREAD_TOML))

    async def test_simple_config_still_builds(self, tmp_path: Path) -> None:
        """load_pipeline on a memory-less config still builds a simple pipeline."""
        pipeline = load_pipeline(_write(tmp_path, _SIMPLE_TOML))
        assert isinstance(pipeline, AnonymizationPipeline)
        result = await pipeline.anonymize("hi Patrick")
        assert "<<PERSON:1>>" in result.text
