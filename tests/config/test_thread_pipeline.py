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


class TestTokenMemoTtl:
    """The top-level scalar bounding how long a token map is memoized.

    It is a top-level scalar, so it is prepended to the config: written after a
    section header it would land inside that section and be refused as an extra
    key, which is TOML rather than a rule of this setting.
    """

    def test_a_ttl_reaches_the_pipeline(self, tmp_path: Path) -> None:
        """token_memo_ttl is forwarded to the thread pipeline it bounds."""
        config = "token_memo_ttl = 300.0\n" + _THREAD_TOML
        pipeline = load_thread_pipeline(_write(tmp_path, config))
        assert pipeline._token_memo_ttl == 300.0

    def test_a_ttl_without_a_memory_is_refused(self, tmp_path: Path) -> None:
        """A memo ttl with no memory raises rather than be silently ignored."""
        config = "token_memo_ttl = 300.0\n" + _SIMPLE_TOML
        with pytest.raises(ConfigError, match="token_memo_ttl"):
            load_pipeline(_write(tmp_path, config))

    def test_a_non_positive_ttl_is_refused(self, tmp_path: Path) -> None:
        """A ttl of zero or less names no window, so it fails validation."""
        config = "token_memo_ttl = 0\n" + _THREAD_TOML
        with pytest.raises(ConfigError):
            load_thread_pipeline(_write(tmp_path, config))


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
