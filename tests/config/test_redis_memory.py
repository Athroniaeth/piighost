"""Tests for the Redis memory config and the promoted memory union."""

import base64
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from piighost.config import load_thread_pipeline
from piighost.config.models.memory import (
    InMemoryConfig,
    MemoryConfig,
    RedisMemoryConfig,
)
from piighost.conversation_memory import RedisConversationMemory
from piighost.pipeline import ThreadAnonymizationPipeline

_KEY_B64 = base64.b64encode(b"0" * 32).decode()
"""A base64-encoded 32-byte AES-GCM key, valid for the cipher env var."""

_REDIS_MEMORY = {
    "type": "redis",
    "url": "redis://localhost:6379/0",
    "hasher": {"type": "sha256"},
    "cipher": {"type": "aesgcm"},
}
"""A redis memory config with a hasher and cipher, reused across the cases."""

_REDIS_TOML = """
[detector]
type = "exact"
values = { Patrick = "PERSON" }

[linker]
type = "exact"

[anonymizer.placeholder]
type = "label_counter"

[memory]
type = "redis"
url = "redis://localhost:6379/0"

[memory.hasher]
type = "sha256"

[memory.cipher]
type = "aesgcm"
"""
"""A full TOML thread-pipeline config backed by a redis memory."""


def _write(tmp_path: Path, text: str) -> Path:
    """Write text to a config.toml under tmp_path and return the path."""
    path = tmp_path / "config.toml"
    path.write_text(text)
    return path


class TestRedisMemoryConfig:
    def test_builds_a_redis_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The redis config builds a RedisConversationMemory offline."""
        monkeypatch.setenv("PIIGHOST_HASH_PEPPER", "secret")
        monkeypatch.setenv("PIIGHOST_CIPHER_KEY", _KEY_B64)
        config = RedisMemoryConfig.model_validate(_REDIS_MEMORY)
        assert isinstance(config.build(), RedisConversationMemory)


class TestMemoryUnion:
    def test_dispatches_in_memory(self) -> None:
        """The in_memory type dispatches to InMemoryConfig."""
        adapter = TypeAdapter(MemoryConfig)
        parsed = adapter.validate_python({"type": "in_memory"})
        assert isinstance(parsed, InMemoryConfig)

    def test_dispatches_redis(self) -> None:
        """The redis type dispatches to RedisMemoryConfig."""
        adapter = TypeAdapter(MemoryConfig)
        assert isinstance(adapter.validate_python(_REDIS_MEMORY), RedisMemoryConfig)


class TestLoadRedisThreadPipeline:
    def test_builds_a_thread_pipeline_with_redis(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """load_thread_pipeline builds a thread pipeline over a redis memory."""
        monkeypatch.setenv("PIIGHOST_HASH_PEPPER", "secret")
        monkeypatch.setenv("PIIGHOST_CIPHER_KEY", _KEY_B64)
        pipeline = load_thread_pipeline(_write(tmp_path, _REDIS_TOML))
        assert isinstance(pipeline, ThreadAnonymizationPipeline)
        assert isinstance(pipeline.memory, RedisConversationMemory)
