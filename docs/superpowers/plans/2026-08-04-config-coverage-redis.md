# Config Coverage C2: Redis Memory and Crypto Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a TOML config describe a Redis-backed thread pipeline by adding hasher and cipher config models (secrets from the environment) and a RedisMemoryConfig, promoting MemoryConfig to a discriminated union.

**Architecture:** New `hasher.py` (sha256/argon2 union) and `cipher.py` (aesgcm alias) config modules, each reading its secret from an env var at build() and raising ConfigError when absent. `memory.py` gains a RedisMemoryConfig combining a URL, a hasher, and a cipher, and MemoryConfig becomes `in_memory | redis`.

**Tech Stack:** Python 3.11+, pydantic. Dev has redis, cryptography, and argon2, and `Redis.from_url` does not connect, so every build() is tested offline.

---

## Conventions

- Run with `uv run --no-sync`. Before each pytest run: `find src tests -name __pycache__ -type d -exec rm -rf {} +`.
- English only. Docstrings plain prose + bullet lists (no markdown/RST). No em dash. No `from __future__`. Native 3.11+ typing. Conventional Commits. Do NOT push. Do NOT create `__init__.py` under `tests/`.
- ANN enforced on src and tests.
- Ports (`AnyHasher`, `AnyCipher`, `AnyConversationMemory`) imported at module top; concrete classes and `redis.asyncio.Redis` imported LAZILY inside build().
- Module secret-name constants carry attached docstrings (rule 24).

## Verified facts (rely on these)

- `Sha256Hasher(pepper: str)` (via `BaseHasher.__init__(pepper)`, refuses empty), in `piighost.crypto.hasher.sha256`; HMAC-SHA256, stdlib, NO extra.
- `Argon2Hasher(pepper: str, *, time_cost=2, memory_cost=19456, parallelism=1, hash_length=32)` in `piighost.crypto.hasher.argon2id`; extra `argon2`.
- `AesGcmCipher(key: bytes)` in `piighost.crypto.cipher.aesgcm`; valid key lengths 16/24/32 bytes, else raises `InvalidKeyLengthError` (a PIIGhostError). Extra `crypto`.
- Ports: `AnyHasher` in `piighost.crypto.hasher.base`; `AnyCipher` in `piighost.crypto.cipher.base`; `AnyConversationMemory` in `piighost.conversation_memory.base`.
- `RedisConversationMemory(client, hasher, cipher, namespace="piighost", ttl=None)` in `piighost.conversation_memory` (lazy export, extra `redis`). Constructing an instance does not connect.
- `redis.asyncio.Redis.from_url(url)` builds a client offline (no connection until first command).
- Current `config/models/memory.py` holds `InMemoryConfig` and `MemoryConfig = InMemoryConfig`. `settings.py` imports `MemoryConfig` and types `PipelineConfig.memory: MemoryConfig | None`; changing MemoryConfig to a union in memory.py needs NO settings.py edit.
- `ConfigError` exists in `piighost.exceptions`. `base64.b64decode(s, validate=True)` raises `binascii.Error` on invalid base64.

---

### Task 1: Hasher and cipher config models

**Files:**
- Create: `src/piighost/config/models/hasher.py`
- Create: `src/piighost/config/models/cipher.py`
- Test: `tests/config/test_crypto_models.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/config/test_crypto_models.py`:

```python
"""Tests for the hasher and cipher config models."""

import base64

import pytest
from pydantic import TypeAdapter

from piighost.config.models.cipher import AesGcmCipherConfig
from piighost.config.models.hasher import (
    Argon2HasherConfig,
    HasherConfig,
    Sha256HasherConfig,
)
from piighost.crypto.cipher.aesgcm import AesGcmCipher
from piighost.crypto.hasher.argon2id import Argon2Hasher
from piighost.crypto.hasher.sha256 import Sha256Hasher
from piighost.exceptions import ConfigError

_KEY_B64 = base64.b64encode(b"0" * 32).decode()


class TestHasherConfig:
    def test_sha256_builds_with_env_pepper(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The sha256 config builds a Sha256Hasher keyed by the env pepper."""
        monkeypatch.setenv("PIIGHOST_HASH_PEPPER", "secret")
        assert isinstance(Sha256HasherConfig(type="sha256").build(), Sha256Hasher)

    def test_argon2_builds_and_stores_costs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The argon2 config builds an Argon2Hasher and keeps its cost fields."""
        monkeypatch.setenv("PIIGHOST_HASH_PEPPER", "secret")
        config = Argon2HasherConfig(type="argon2", time_cost=3, memory_cost=1024)
        assert config.time_cost == 3
        assert config.memory_cost == 1024
        assert isinstance(config.build(), Argon2Hasher)

    def test_missing_pepper_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A hasher build without the env pepper raises ConfigError."""
        monkeypatch.delenv("PIIGHOST_HASH_PEPPER", raising=False)
        with pytest.raises(ConfigError):
            Sha256HasherConfig(type="sha256").build()

    def test_union_dispatches_on_type(self) -> None:
        """The type discriminant selects the matching hasher config."""
        adapter = TypeAdapter(HasherConfig)
        assert isinstance(
            adapter.validate_python({"type": "argon2"}), Argon2HasherConfig
        )


class TestCipherConfig:
    def test_aesgcm_builds_with_env_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The aesgcm config builds an AesGcmCipher from the base64 env key."""
        monkeypatch.setenv("PIIGHOST_CIPHER_KEY", _KEY_B64)
        assert isinstance(AesGcmCipherConfig(type="aesgcm").build(), AesGcmCipher)

    def test_missing_key_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A cipher build without the env key raises ConfigError."""
        monkeypatch.delenv("PIIGHOST_CIPHER_KEY", raising=False)
        with pytest.raises(ConfigError):
            AesGcmCipherConfig(type="aesgcm").build()

    def test_invalid_base64_key_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cipher build with a non-base64 key raises ConfigError."""
        monkeypatch.setenv("PIIGHOST_CIPHER_KEY", "not valid base64 !!!")
        with pytest.raises(ConfigError):
            AesGcmCipherConfig(type="aesgcm").build()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/config/test_crypto_models.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'piighost.config.models.hasher'`.

- [ ] **Step 3: Create hasher.py**

Create `src/piighost/config/models/hasher.py`:

```python
"""Hasher configuration models, discriminated on type.

The pepper is a secret read from the PIIGHOST_HASH_PEPPER environment variable,
never from the TOML, so it is not committed. build() requires it and raises a
ConfigError when it is unset.
"""

import os
from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.config.models.common import _ComponentConfig
from piighost.crypto.hasher.base import AnyHasher
from piighost.exceptions import ConfigError

_HASH_PEPPER_ENV = "PIIGHOST_HASH_PEPPER"
"""The environment variable holding the pepper that keys every hasher."""


def _read_pepper() -> str:
    """Return the hash pepper from the environment.

    Raises:
        ConfigError: If PIIGHOST_HASH_PEPPER is unset or empty.
    """
    pepper = os.environ.get(_HASH_PEPPER_ENV)
    if not pepper:
        raise ConfigError(
            f"a hasher requires the {_HASH_PEPPER_ENV} environment variable to be set"
        )
    return pepper


class Sha256HasherConfig(_ComponentConfig):
    """Config for the HMAC-SHA256 hasher, a fast keyed digest."""

    type: Literal["sha256"]

    def build(self) -> AnyHasher:
        """Build a Sha256Hasher keyed by the environment pepper."""
        from piighost.crypto.hasher.sha256 import Sha256Hasher

        return Sha256Hasher(_read_pepper())


class Argon2HasherConfig(_ComponentConfig):
    """Config for the Argon2id hasher, a slow memory-hard digest.

    Attributes:
        time_cost: The number of Argon2 iterations.
        memory_cost: The memory in kibibytes Argon2 uses.
        parallelism: The number of parallel lanes.
        hash_length: The digest length in bytes.
    """

    type: Literal["argon2"]
    time_cost: int = Field(default=2, ge=1)
    memory_cost: int = Field(default=19456, ge=1)
    parallelism: int = Field(default=1, ge=1)
    hash_length: int = Field(default=32, ge=1)

    def build(self) -> AnyHasher:
        """Build an Argon2Hasher keyed by the environment pepper."""
        from piighost.crypto.hasher.argon2id import Argon2Hasher

        return Argon2Hasher(
            _read_pepper(),
            time_cost=self.time_cost,
            memory_cost=self.memory_cost,
            parallelism=self.parallelism,
            hash_length=self.hash_length,
        )


HasherConfig = Annotated[
    Sha256HasherConfig | Argon2HasherConfig,
    Discriminator("type"),
]
```

- [ ] **Step 4: Create cipher.py**

Create `src/piighost/config/models/cipher.py`:

```python
"""Cipher configuration model.

The key is a secret read from the PIIGHOST_CIPHER_KEY environment variable,
base64-encoded, never from the TOML. build() requires it and raises a ConfigError
when it is unset or not valid base64.
"""

import base64
import binascii
import os
from typing import Literal

from piighost.config.models.common import _ComponentConfig
from piighost.crypto.cipher.base import AnyCipher
from piighost.exceptions import ConfigError

_CIPHER_KEY_ENV = "PIIGHOST_CIPHER_KEY"
"""The environment variable holding the base64 AES key the cipher uses."""


class AesGcmCipherConfig(_ComponentConfig):
    """Config for the AES-GCM cipher, authenticated encryption of stored values."""

    type: Literal["aesgcm"]

    def build(self) -> AnyCipher:
        """Build an AesGcmCipher from the base64 key in the environment.

        Raises:
            ConfigError: If PIIGHOST_CIPHER_KEY is unset or not valid base64.
        """
        from piighost.crypto.cipher.aesgcm import AesGcmCipher

        encoded = os.environ.get(_CIPHER_KEY_ENV)
        if not encoded:
            raise ConfigError(
                f"the cipher requires the {_CIPHER_KEY_ENV} environment variable "
                "to be set"
            )
        try:
            key = base64.b64decode(encoded, validate=True)
        except binascii.Error as exc:
            raise ConfigError(f"{_CIPHER_KEY_ENV} must be valid base64: {exc}") from exc
        return AesGcmCipher(key)


CipherConfig = AesGcmCipherConfig
"""The cipher configuration.

A plain alias while one cipher exists; it becomes a discriminated union when a
second cipher lands.
"""
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/config/test_crypto_models.py -q`
Expected: PASS (7 tests).

- [ ] **Step 6: Lint, types, commit**

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: clean, 0 errors.

```bash
git add src/piighost/config/models/hasher.py src/piighost/config/models/cipher.py tests/config/test_crypto_models.py
git commit -m "feat(config): add hasher and cipher config models"
```

---

### Task 2: Redis memory config and the memory union

**Files:**
- Modify: `src/piighost/config/models/memory.py`
- Test: `tests/config/test_redis_memory.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/config/test_redis_memory.py`:

```python
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

_REDIS_MEMORY = {
    "type": "redis",
    "url": "redis://localhost:6379/0",
    "hasher": {"type": "sha256"},
    "cipher": {"type": "aesgcm"},
}

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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/config/test_redis_memory.py -q`
Expected: FAIL with `ImportError: cannot import name 'RedisMemoryConfig'`.

- [ ] **Step 3: Rewrite memory.py**

Replace the ENTIRE contents of `src/piighost/config/models/memory.py` with:

```python
"""Conversation memory configuration models, discriminated on type."""

from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.config.models.cipher import CipherConfig
from piighost.config.models.common import _ComponentConfig
from piighost.config.models.hasher import HasherConfig
from piighost.conversation_memory.base import AnyConversationMemory


class InMemoryConfig(_ComponentConfig):
    """Config for the in-memory conversation memory, a process-local store."""

    type: Literal["in_memory"]

    def build(self) -> AnyConversationMemory:
        """Build an InMemoryConversationMemory."""
        from piighost.conversation_memory import InMemoryConversationMemory

        return InMemoryConversationMemory()


class RedisMemoryConfig(_ComponentConfig):
    """Config for the Redis conversation memory, persistent and multi-worker.

    Attributes:
        url: The Redis connection URL the client is built from.
        namespace: The key prefix isolating this library's keys in Redis.
        ttl: The seconds a stored message lives, or None to keep it until eviction.
        hasher: The hasher keying each message into its storage key.
        cipher: The cipher encrypting each stored value.
    """

    type: Literal["redis"]
    url: str
    namespace: str = "piighost"
    ttl: int | None = Field(default=None, ge=1)
    hasher: HasherConfig
    cipher: CipherConfig

    def build(self) -> AnyConversationMemory:
        """Build a RedisConversationMemory over a client built from the URL."""
        from redis.asyncio import Redis

        from piighost.conversation_memory import RedisConversationMemory

        client = Redis.from_url(self.url)
        return RedisConversationMemory(
            client,
            self.hasher.build(),
            self.cipher.build(),
            namespace=self.namespace,
            ttl=self.ttl,
        )


MemoryConfig = Annotated[
    InMemoryConfig | RedisMemoryConfig,
    Discriminator("type"),
]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/config/ -q`
Expected: PASS. The C1 thread tests (which use `[memory] type=in_memory`) stay green because in_memory still dispatches through the promoted union.

- [ ] **Step 5: Full suite, lint, types**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest -q`
Expected: full suite PASS.

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: clean, 0 errors.

- [ ] **Step 6: Commit**

```bash
git add src/piighost/config/models/memory.py tests/config/test_redis_memory.py
git commit -m "feat(config): add the redis memory config and the memory union"
```

---

## Notes for the implementer

- The pepper (`PIIGHOST_HASH_PEPPER`) and cipher key (`PIIGHOST_CIPHER_KEY`, base64) are secrets read from the environment at build() time, never TOML fields. A missing secret raises `ConfigError` (fail closed at build, not an opaque error later). This mirrors the moderation guard from an earlier sub-lot.
- A base64-decoded key of the wrong length is left to `AesGcmCipher` to reject with `InvalidKeyLengthError` (already a PIIGhostError); do not add a length check in the config.
- All three extras (redis, cryptography, argon2) are in the dev env and `Redis.from_url` does not connect, so build() runs offline and is fully tested. No importorskip or parse-only shortcuts are needed here.
- Promoting `MemoryConfig` to a union needs NO settings.py change: settings.py imports the name `MemoryConfig`, which now resolves to the union.
- Keep the one-way coupling: config imports core, never the reverse. No new exception (ConfigError exists), nothing added to PUBLIC_API.
