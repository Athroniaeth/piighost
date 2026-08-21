# SQLAlchemy conversation memory + optional at-rest crypto — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `SqlAlchemyConversationMemory`, a durable `AnyConversationMemory` backend on async SQLAlchemy (sqlite + PostgreSQL), and make at-rest crypto optional across every persistent backend (retrofitting Redis), with a `PIIGhostSecurityWarning` when a networked backend runs without crypto.

**Architecture:** A third backend beside `InMemoryConversationMemory` and `RedisConversationMemory`, over an injected async SQLAlchemy engine, using SQLAlchemy Core (a `Table` on a per-instance `MetaData`, so the table name is configurable). Crypto (an `AnyHasher` for the message key, an `AnyCipher` for the detections) is opt-in; both-or-neither. A shared `warn_plaintext` helper emits the warning for networked backends without crypto.

**Tech Stack:** SQLAlchemy 2.0 async, aiosqlite (dev + tests), asyncpg (PostgreSQL). Reuses `AnyHasher` / `AnyCipher` and the pydantic config layer.

Reference: spec at `docs/superpowers/specs/2026-08-16-sqlalchemy-conversation-memory-design.md`.

---

## File structure

- Modify `src/piighost/exceptions.py`: add `PIIGhostSecurityWarning(UserWarning)`.
- Modify `src/piighost/conversation_memory/base.py`: add the `warn_plaintext(backend)` helper + doc URL constant.
- Modify `src/piighost/conversation_memory/redis_backend.py`: optional hasher/cipher, sha256 key fallback, warning.
- Create `src/piighost/conversation_memory/sqlalchemy_backend.py`: the backend.
- Modify `src/piighost/conversation_memory/__init__.py`: lazy export `SqlAlchemyConversationMemory`.
- Modify `src/piighost/config/models/memory.py`: optional crypto on `RedisMemoryConfig`, add `SqlAlchemyMemoryConfig`, extend `MemoryConfig`.
- Modify `pyproject.toml`: add the `sqlalchemy` extra, add to `all` and the dev group.
- Create `tests/conversation_memory/test_sqlalchemy.py`.
- Modify `tests/conversation_memory/test_redis.py`: plaintext + warning.
- Create `tests/config/test_sqlalchemy_memory.py`.
- Modify `docs/en/security.md` + `docs/fr/security.md`: backend comparison + warning.

---

## Task 1: PIIGhostSecurityWarning + warn_plaintext helper

**Files:**
- Modify: `src/piighost/exceptions.py`
- Modify: `src/piighost/conversation_memory/base.py`
- Test: `tests/conversation_memory/test_base.py` (create if absent)

- [ ] **Step 1: Write the failing test**

Create/extend `tests/conversation_memory/test_base.py`:

```python
"""Tests for the conversation memory shared helpers."""

import warnings

import pytest

from piighost.conversation_memory.base import warn_plaintext
from piighost.exceptions import PIIGhostSecurityWarning


class TestWarnPlaintext:
    def test_emits_a_security_warning_naming_the_backend_and_doc(self) -> None:
        """warn_plaintext warns with the backend name and the security doc URL."""
        with pytest.warns(PIIGhostSecurityWarning) as record:
            warn_plaintext("RedisConversationMemory")
        message = str(record[0].message)
        assert "RedisConversationMemory" in message
        assert "https://athroniaeth.github.io/piighost/security/" in message
```

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest tests/conversation_memory/test_base.py -q`
Expected: FAIL (ImportError: cannot import name `warn_plaintext` / `PIIGhostSecurityWarning`).

- [ ] **Step 3: Add the warning class**

In `src/piighost/exceptions.py`, append at the end of the file:

```python
class PIIGhostSecurityWarning(UserWarning):
    """Warned when a persistent backend stores PII in clear without crypto.

    A networked or shared store built without a hasher and cipher keeps PII
    readable to anyone who reads the store. This warns rather than fails, so a
    knowing plaintext setup still works while a forgotten one is loud. It is a
    UserWarning, not a PIIGhostError, since it is a heads-up and not a failure.
    """
```

- [ ] **Step 4: Add the helper**

In `src/piighost/conversation_memory/base.py`, add near the top after the existing imports:

```python
import warnings

from piighost.exceptions import PIIGhostSecurityWarning

_SECURITY_DOC_URL = "https://athroniaeth.github.io/piighost/security/"
"""Documentation page explaining the at-rest crypto options for a backend."""


def warn_plaintext(backend: str) -> None:
    """Warn that a networked backend stores PII in clear, no crypto configured.

    Called at construction by a persistent backend built without a hasher and
    cipher, when its store is networked or shared. It nudges toward configuring
    crypto rather than failing, so a knowing plaintext setup still runs.
    """
    warnings.warn(
        f"{backend} was built without a hasher or cipher, so it stores PII in "
        f"clear. For a networked or shared store, configure a hasher and a "
        f"cipher. See {_SECURITY_DOC_URL}",
        PIIGhostSecurityWarning,
        stacklevel=3,
    )
```

- [ ] **Step 5: Run it to see it pass**

Run: `uv run pytest tests/conversation_memory/test_base.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/piighost/exceptions.py src/piighost/conversation_memory/base.py tests/conversation_memory/test_base.py
git commit -m "feat(memory): add PIIGhostSecurityWarning and the warn_plaintext helper"
```

---

## Task 2: Redis backend — optional crypto + warning

**Files:**
- Modify: `src/piighost/conversation_memory/redis_backend.py`
- Test: `tests/conversation_memory/test_redis.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/conversation_memory/test_redis.py` (it uses `fakeredis`; match the file's existing fixture for building a client — reuse its `_memory()`/client helper, here shown building directly):

```python
class TestRedisPlaintext:
    async def test_round_trips_without_crypto(self) -> None:
        """Without a hasher or cipher, detections still round-trip in clear."""
        import fakeredis.aioredis

        from piighost.conversation_memory import RedisConversationMemory
        from piighost.components.detector import ExactMatchDetector

        client = fakeredis.aioredis.FakeRedis()
        with pytest.warns(PIIGhostSecurityWarning):
            memory = RedisConversationMemory(client)
        detections = await ExactMatchDetector({"Emma": "PERSON"}).detect("Hi Emma")
        await memory.remember("t1", "Hi Emma", detections)
        assert await memory.get_detections("t1", "Hi Emma") == detections

    def test_exactly_one_of_hasher_cipher_is_refused(self) -> None:
        """Providing only a hasher, or only a cipher, is a misuse."""
        import fakeredis.aioredis

        from piighost.conversation_memory import RedisConversationMemory
        from piighost.crypto.hasher import HmacHasher

        client = fakeredis.aioredis.FakeRedis()
        with pytest.raises(ValueError):
            RedisConversationMemory(client, hasher=HmacHasher("pepper"))
```

Add the import at the top of the test file if absent:

```python
from piighost.exceptions import PIIGhostSecurityWarning
```

Note: confirm the concrete hasher name by reading `src/piighost/crypto/hasher/__init__.py`; use whatever the existing Redis tests import (adjust `HmacHasher` if the export differs).

- [ ] **Step 2: Run to see it fail**

Run: `uv run pytest tests/conversation_memory/test_redis.py -q -k "Plaintext or refused"`
Expected: FAIL (TypeError: missing hasher/cipher, or no warning).

- [ ] **Step 3: Make hasher/cipher optional + warn**

In `src/piighost/conversation_memory/redis_backend.py`:

Add imports near the top (after the existing imports):

```python
import hashlib

from piighost.conversation_memory.base import Forgotten, MessageRole, warn_plaintext
```

(Replace the existing `from piighost.conversation_memory.base import Forgotten, MessageRole` line with the one above so `warn_plaintext` comes in.)

Change `__init__`:

```python
    def __init__(
        self,
        client: Redis,
        hasher: AnyHasher | None = None,
        cipher: AnyCipher | None = None,
        namespace: str = _DEFAULT_NAMESPACE,
        ttl: int | None = None,
    ) -> None:
        """Store the client, the optional crypto, and the namespace and TTL.

        A hasher keys each message and a cipher encrypts each value; pass both to
        store securely, or neither to store in clear. Passing exactly one is a
        misuse. Redis is a networked store, so a plaintext backend warns.
        """
        if (hasher is None) != (cipher is None):
            raise ValueError("Provide both a hasher and a cipher, or neither")
        self._client = client
        self._hasher = hasher
        self._cipher = cipher
        self.namespace = namespace
        self._ttl = ttl
        if hasher is None:
            warn_plaintext("RedisConversationMemory")
```

Add a digest helper and use it plus conditional crypto. Add this method:

```python
    def _digest(self, message: str) -> str:
        """Key a message: the security hasher if set, else a plain SHA-256."""
        if self._hasher is not None:
            return self._hasher.hash(message)
        return hashlib.sha256(message.encode()).hexdigest()

    def _encrypt(self, data: bytes) -> bytes:
        """Encrypt a value if a cipher is set, else pass it through in clear."""
        return self._cipher.encrypt(data) if self._cipher is not None else data

    def _decrypt(self, data: bytes) -> bytes:
        """Decrypt a value if a cipher is set, else pass it through in clear."""
        return self._cipher.decrypt(data) if self._cipher is not None else data
```

Then, in `remember`, `get_detections`, `get_provenance`, and `forget`, replace:
- every `self._hasher.hash(message)` with `self._digest(message)`,
- every `self._cipher.encrypt(json_detections)` with `self._encrypt(json_detections)`,
- every `self._cipher.decrypt(ciphertext)` with `self._decrypt(ciphertext)`.

- [ ] **Step 4: Run to see it pass**

Run: `uv run pytest tests/conversation_memory/test_redis.py -q`
Expected: PASS (existing crypto tests still pass, new plaintext + refusal tests pass).

- [ ] **Step 5: Commit**

```bash
git add src/piighost/conversation_memory/redis_backend.py tests/conversation_memory/test_redis.py
git commit -m "feat(memory): make Redis crypto optional, warn on plaintext"
```

---

## Task 3: The sqlalchemy extra

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the extra**

In `pyproject.toml`, under `[project.optional-dependencies]`, add:

```toml
sqlalchemy = [
    "sqlalchemy[asyncio]>=2.0",
    "aiosqlite>=0.19",
    "asyncpg>=0.29",
]
```

Add `sqlalchemy` to the `all` extra's inner list, e.g.:

```toml
all = [
    "piighost[gliner2,redis,middleware,pydantic-ai,client,spacy,transformers,llm,observation,fuzzy,config,argon2,crypto,mistral,sqlalchemy]",
]
```

In `[dependency-groups] dev`, add:

```toml
    "sqlalchemy[asyncio]>=2.0",
    "aiosqlite>=0.19",
    "asyncpg>=0.29",
```

- [ ] **Step 2: Sync and verify the lock**

Run: `uv sync --extra sqlalchemy` then `uv lock --check`
Expected: resolves; lock is current.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add the sqlalchemy optional extra"
```

---

## Task 4: SqlAlchemyConversationMemory backend

**Files:**
- Create: `src/piighost/conversation_memory/sqlalchemy_backend.py`
- Modify: `src/piighost/conversation_memory/__init__.py`
- Test: `tests/conversation_memory/test_sqlalchemy.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/conversation_memory/test_sqlalchemy.py`:

```python
"""Tests for the SQLAlchemy conversation memory backend."""

import pytest

pytest.importorskip("sqlalchemy")

import pytest_asyncio  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from piighost.components.detector import ExactMatchDetector  # noqa: E402
from piighost.conversation_memory import (  # noqa: E402
    AnyConversationMemory,
    SqlAlchemyConversationMemory,
)
from piighost.conversation_memory.base import MessageRole  # noqa: E402
from piighost.exceptions import PIIGhostSecurityWarning  # noqa: E402


@pytest_asyncio.fixture
async def memory(tmp_path):
    """Build a schema-created sqlite-backed memory over a temp file database."""
    url = f"sqlite+aiosqlite:///{tmp_path / 'memory.db'}"
    engine = create_async_engine(url)
    store = SqlAlchemyConversationMemory(engine)
    await store.create_schema()
    yield store
    await engine.dispose()


class TestConformance:
    def test_satisfies_the_port(self, memory) -> None:
        """The backend is an AnyConversationMemory."""
        assert isinstance(memory, AnyConversationMemory)


class TestRoundTrip:
    async def test_remembers_and_returns_a_message(self, memory) -> None:
        """A remembered message's detections come back for that message."""
        detections = await ExactMatchDetector({"Emma": "PERSON"}).detect("Hi Emma")
        await memory.remember("t1", "Hi Emma", detections)
        assert await memory.get_detections("t1", "Hi Emma") == detections

    async def test_unseen_message_returns_none(self, memory) -> None:
        """A message never remembered returns None so detection runs."""
        assert await memory.get_detections("t1", "never") is None

    async def test_whole_thread_unions_in_first_seen_order(self, memory) -> None:
        """With no message, the union of every message's detections is returned."""
        first = await ExactMatchDetector({"Emma": "PERSON"}).detect("Hi Emma")
        second = await ExactMatchDetector({"Liam": "PERSON"}).detect("and Liam")
        await memory.remember("t1", "Hi Emma", first)
        await memory.remember("t1", "and Liam", second)
        assert await memory.get_detections("t1") == first + second

    async def test_rewriting_a_message_keeps_first_seen_order(self, memory) -> None:
        """Re-remembering a message updates it in place without reordering."""
        emma = await ExactMatchDetector({"Emma": "PERSON"}).detect("Hi Emma")
        liam = await ExactMatchDetector({"Liam": "PERSON"}).detect("and Liam")
        await memory.remember("t1", "Hi Emma", emma)
        await memory.remember("t1", "and Liam", liam)
        await memory.remember("t1", "Hi Emma", emma)  # rewrite
        assert await memory.get_detections("t1") == emma + liam


class TestProvenance:
    async def test_first_occurrence_role_wins(self, memory) -> None:
        """A value keeps the role of its earliest message."""
        detections = await ExactMatchDetector({"Emma": "PERSON"}).detect("Emma")
        await memory.remember("t1", "Emma", detections, role=MessageRole.ASSISTANT)
        await memory.remember("t1", "Emma again", detections, role=MessageRole.USER)
        assert (await memory.get_provenance("t1"))["emma"] is MessageRole.ASSISTANT


class TestForget:
    async def test_forget_reports_and_erases(self, memory) -> None:
        """Forgetting a thread erases it and reports the counts dropped."""
        detections = await ExactMatchDetector({"Emma": "PERSON"}).detect("Hi Emma")
        await memory.remember("t1", "Hi Emma", detections)
        forgotten = await memory.forget("t1")
        assert forgotten.messages == 1
        assert forgotten.detections == 1
        assert await memory.get_detections("t1") == []

    async def test_forget_unknown_thread_reports_zero(self, memory) -> None:
        """Forgetting a thread never written drops nothing."""
        forgotten = await memory.forget("ghost")
        assert forgotten.messages == 0
        assert forgotten.detections == 0


class TestCrypto:
    async def test_exactly_one_of_hasher_cipher_is_refused(self, tmp_path) -> None:
        """Providing only a hasher, or only a cipher, is a misuse."""
        from piighost.crypto.hasher import HmacHasher

        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'x.db'}")
        with pytest.raises(ValueError):
            SqlAlchemyConversationMemory(engine, hasher=HmacHasher("pepper"))
        await engine.dispose()


class TestWarning:
    async def test_networked_dialect_without_crypto_warns(self) -> None:
        """A postgres engine with no crypto warns; building it does not connect."""
        engine = create_async_engine("postgresql+asyncpg://u:p@localhost/db")
        with pytest.warns(PIIGhostSecurityWarning):
            SqlAlchemyConversationMemory(engine)
        await engine.dispose()

    def test_sqlite_without_crypto_is_silent(self, memory) -> None:
        """A sqlite backend without crypto does not warn (local dev)."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("error", PIIGhostSecurityWarning)
            # building `memory` in the fixture already succeeded without warning
            assert isinstance(memory, SqlAlchemyConversationMemory)
```

Note: confirm the concrete hasher export name in `src/piighost/crypto/hasher/__init__.py` and adjust `HmacHasher` if needed. `pytest_asyncio` is already a dev dependency.

- [ ] **Step 2: Run to see it fail**

Run: `uv run pytest tests/conversation_memory/test_sqlalchemy.py -q`
Expected: FAIL (cannot import `SqlAlchemyConversationMemory`).

- [ ] **Step 3: Write the backend**

Create `src/piighost/conversation_memory/sqlalchemy_backend.py`:

```python
"""SQLAlchemy conversation memory backend (optional dependency: sqlalchemy).

This module needs the sqlalchemy package. It is guarded so importing it without
the dependency raises an ImportError pointing at the extra to install. The core
conversation_memory package never imports it eagerly.

Layout, one row per thread message. The message is hashed into a digest and the
detections are optionally encrypted, so a store leak reveals neither the message
nor the PII when crypto is configured:

  {table}(id, thread_id, message_digest, role, detections, detection_count)

The thread_id stays clear so a thread can be enumerated and forgotten; the
autoincrement id gives first-seen order.
"""

import hashlib
import importlib.util
import json

from piighost.conversation_memory.base import Forgotten, MessageRole, warn_plaintext
from piighost.crypto.cipher.base import AnyCipher
from piighost.crypto.hasher.base import AnyHasher
from piighost.models import Detection

if importlib.util.find_spec("sqlalchemy") is None:
    raise ImportError(
        "SqlAlchemyConversationMemory requires the sqlalchemy package. "
        "Install it with: pip install piighost[sqlalchemy]"
    )

from sqlalchemy import (  # noqa: E402
    Column,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    delete,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncEngine  # noqa: E402

_DEFAULT_TABLE = "piighost_conversation_messages"
"""Default table name holding every thread's message detections."""


class SqlAlchemyConversationMemory:
    """Persist each thread's message detections in a SQL table, durably.

    A durable AnyConversationMemory backend over an injected async engine, for
    long conversations that outlive a process. The message is keyed by a digest
    and the detections are stored in one column, optionally encrypted. Crypto is
    all-or-nothing: pass both a hasher and a cipher to store securely, or neither
    to store in clear. A networked store without crypto warns at construction.

    The engine is injected and the caller owns its lifecycle. Call create_schema
    once at startup to create the table.

    Attributes:
        table_name: The name of the table this backend reads and writes.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        hasher: AnyHasher | None = None,
        cipher: AnyCipher | None = None,
        table_name: str = _DEFAULT_TABLE,
    ) -> None:
        """Store the engine and optional crypto, and define the table."""
        if (hasher is None) != (cipher is None):
            raise ValueError("Provide both a hasher and a cipher, or neither")
        self._engine = engine
        self._hasher = hasher
        self._cipher = cipher
        self.table_name = table_name
        self._metadata = MetaData()
        self._table = Table(
            table_name,
            self._metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("thread_id", String, nullable=False, index=True),
            Column("message_digest", String, nullable=False),
            Column("role", String, nullable=False),
            Column("detections", LargeBinary, nullable=False),
            Column("detection_count", Integer, nullable=False),
            UniqueConstraint("thread_id", "message_digest"),
        )
        if hasher is None and engine.dialect.name != "sqlite":
            warn_plaintext("SqlAlchemyConversationMemory")

    async def create_schema(self) -> None:
        """Create the table if it does not exist, idempotently."""
        async with self._engine.begin() as conn:
            await conn.run_sync(self._metadata.create_all)

    def _digest(self, message: str) -> str:
        """Key a message: the security hasher if set, else a plain SHA-256."""
        if self._hasher is not None:
            return self._hasher.hash(message)
        return hashlib.sha256(message.encode()).hexdigest()

    def _serialize(self, detections: list[Detection]) -> bytes:
        """Serialize detections to JSON bytes, encrypting when a cipher is set."""
        blob = json.dumps([d.to_dict() for d in detections]).encode()
        return self._cipher.encrypt(blob) if self._cipher is not None else blob

    def _deserialize(self, data: bytes) -> list[Detection]:
        """Rebuild detections from stored bytes, decrypting when a cipher is set."""
        raw = self._cipher.decrypt(data) if self._cipher is not None else data
        return [Detection.from_dict(item) for item in json.loads(raw)]

    async def remember(
        self,
        thread_id: str,
        message: str,
        detections: list[Detection],
        role: MessageRole = MessageRole.USER,
    ) -> None:
        """Cache the detections found in a message, replacing any prior entry."""
        digest = self._digest(message)
        blob = self._serialize(detections)
        table = self._table
        async with self._engine.begin() as conn:
            found = (
                await conn.execute(
                    select(table.c.id).where(
                        table.c.thread_id == thread_id,
                        table.c.message_digest == digest,
                    )
                )
            ).first()
            values = {
                "role": role.value,
                "detections": blob,
                "detection_count": len(detections),
            }
            if found is None:
                await conn.execute(
                    insert(table).values(
                        thread_id=thread_id,
                        message_digest=digest,
                        **values,
                    )
                )
            else:
                await conn.execute(
                    update(table).where(table.c.id == found.id).values(**values)
                )

    async def get_detections(
        self,
        thread_id: str,
        message: str | None = None,
    ) -> list[Detection] | None:
        """Return a thread's detections, for one message or the whole thread."""
        table = self._table
        if message is not None:
            digest = self._digest(message)
            async with self._engine.connect() as conn:
                row = (
                    await conn.execute(
                        select(table.c.detections).where(
                            table.c.thread_id == thread_id,
                            table.c.message_digest == digest,
                        )
                    )
                ).first()
            if row is None:
                return None
            return self._deserialize(row.detections)

        async with self._engine.connect() as conn:
            rows = (
                await conn.execute(
                    select(table.c.detections)
                    .where(table.c.thread_id == thread_id)
                    .order_by(table.c.id)
                )
            ).all()
        detections: list[Detection] = []
        for row in rows:
            detections.extend(self._deserialize(row.detections))
        return detections

    async def get_provenance(self, thread_id: str) -> dict[str, MessageRole]:
        """Return the first-occurrence role of every value in the thread."""
        table = self._table
        async with self._engine.connect() as conn:
            rows = (
                await conn.execute(
                    select(table.c.role, table.c.detections)
                    .where(table.c.thread_id == thread_id)
                    .order_by(table.c.id)
                )
            ).all()
        provenance: dict[str, MessageRole] = {}
        for row in rows:
            role = MessageRole(row.role)
            for detection in self._deserialize(row.detections):
                provenance.setdefault(detection.text.casefold(), role)
        return provenance

    async def forget(self, thread_id: str) -> Forgotten:
        """Erase a thread and report how many messages and detections dropped."""
        table = self._table
        async with self._engine.begin() as conn:
            totals = (
                await conn.execute(
                    select(
                        func.count(),
                        func.coalesce(func.sum(table.c.detection_count), 0),
                    ).where(table.c.thread_id == thread_id)
                )
            ).one()
            await conn.execute(delete(table).where(table.c.thread_id == thread_id))
        return Forgotten(messages=int(totals[0]), detections=int(totals[1]))
```

- [ ] **Step 4: Export it lazily**

In `src/piighost/conversation_memory/__init__.py`, add `"SqlAlchemyConversationMemory"` to `__all__`, and extend `__getattr__`:

```python
    if name == "SqlAlchemyConversationMemory":
        from piighost.conversation_memory.sqlalchemy_backend import (
            SqlAlchemyConversationMemory,
        )

        return SqlAlchemyConversationMemory
```

- [ ] **Step 5: Run to see it pass**

Run: `uv run pytest tests/conversation_memory/test_sqlalchemy.py -q`
Expected: PASS (all classes green).

- [ ] **Step 6: Commit**

```bash
git add src/piighost/conversation_memory/sqlalchemy_backend.py src/piighost/conversation_memory/__init__.py tests/conversation_memory/test_sqlalchemy.py
git commit -m "feat(memory): add the SQLAlchemy conversation memory backend"
```

---

## Task 5: Config models

**Files:**
- Modify: `src/piighost/config/models/memory.py`
- Test: `tests/config/test_sqlalchemy_memory.py`
- Test: `tests/config/test_redis_memory.py` (confirm optional crypto still builds)

- [ ] **Step 1: Write the failing tests**

Create `tests/config/test_sqlalchemy_memory.py`:

```python
"""Tests for the SQLAlchemy memory config model."""

import pytest

pytest.importorskip("sqlalchemy")

from piighost.config.models.memory import SqlAlchemyMemoryConfig  # noqa: E402
from piighost.conversation_memory import SqlAlchemyConversationMemory  # noqa: E402
from piighost.exceptions import ConfigError  # noqa: E402


class TestBuild:
    def test_builds_from_the_url_env_var(self, monkeypatch) -> None:
        """build reads the database URL from the configured env var."""
        monkeypatch.setenv("PIIGHOST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
        config = SqlAlchemyMemoryConfig(type="sqlalchemy")
        memory = config.build()
        assert isinstance(memory, SqlAlchemyConversationMemory)

    def test_missing_url_env_var_raises_config_error(self, monkeypatch) -> None:
        """A missing database URL env var is a configuration error."""
        monkeypatch.delenv("PIIGHOST_DATABASE_URL", raising=False)
        config = SqlAlchemyMemoryConfig(type="sqlalchemy")
        with pytest.raises(ConfigError):
            config.build()
```

- [ ] **Step 2: Run to see it fail**

Run: `uv run pytest tests/config/test_sqlalchemy_memory.py -q`
Expected: FAIL (cannot import `SqlAlchemyMemoryConfig`).

- [ ] **Step 3: Update the config models**

In `src/piighost/config/models/memory.py`:

Make Redis crypto optional — change the two fields on `RedisMemoryConfig`:

```python
    hasher: HasherConfig | None = None
    cipher: CipherConfig | None = None
```

and its `build()` body to build them conditionally:

```python
        hasher = self.hasher.build() if self.hasher is not None else None
        cipher = self.cipher.build() if self.cipher is not None else None
        return RedisConversationMemory(
            client,
            hasher,
            cipher,
            namespace=self.namespace,
            ttl=self.ttl,
        )
```

Add the new config class after `RedisMemoryConfig`:

```python
class SqlAlchemyMemoryConfig(_ComponentConfig):
    """Config for the SQLAlchemy conversation memory, durable and long-lived.

    Attributes:
        url_env: The environment variable holding the database URL, read at
            build time so the URL and its password stay out of the config file.
        table_name: The table the backend reads and writes.
        hasher: The optional hasher keying each message into its digest.
        cipher: The optional cipher encrypting each stored value.
    """

    type: Literal["sqlalchemy"]
    url_env: str = "PIIGHOST_DATABASE_URL"
    table_name: str = "piighost_conversation_messages"
    hasher: HasherConfig | None = None
    cipher: CipherConfig | None = None

    def build(self) -> AnyConversationMemory:
        """Build a SqlAlchemyConversationMemory over an engine from the URL env."""
        import os

        from sqlalchemy.ext.asyncio import create_async_engine

        from piighost.conversation_memory import SqlAlchemyConversationMemory
        from piighost.exceptions import ConfigError

        url = os.environ.get(self.url_env)
        if not url:
            raise ConfigError(
                f"The SQLAlchemy memory needs the {self.url_env} environment "
                f"variable holding the database URL"
            )
        engine = create_async_engine(url)
        hasher = self.hasher.build() if self.hasher is not None else None
        cipher = self.cipher.build() if self.cipher is not None else None
        return SqlAlchemyConversationMemory(
            engine,
            hasher,
            cipher,
            table_name=self.table_name,
        )
```

Extend the discriminated union:

```python
MemoryConfig = Annotated[
    InMemoryConfig | RedisMemoryConfig | SqlAlchemyMemoryConfig,
    Discriminator("type"),
]
```

- [ ] **Step 4: Run to see it pass**

Run: `uv run pytest tests/config/test_sqlalchemy_memory.py tests/config/test_redis_memory.py -q`
Expected: PASS (new config builds; Redis config still builds, now with optional crypto).

- [ ] **Step 5: Commit**

```bash
git add src/piighost/config/models/memory.py tests/config/test_sqlalchemy_memory.py
git commit -m "feat(config): add SqlAlchemyMemoryConfig, make Redis crypto optional"
```

---

## Task 6: Documentation (EN + FR, mirrored)

**Files:**
- Modify: `docs/en/security.md`
- Modify: `docs/fr/security.md`

- [ ] **Step 1: Update the EN security page**

Read `docs/en/security.md`, find the memory-backend comparison section, and add a row/paragraph for `SqlAlchemyConversationMemory` (durable, sqlite + PostgreSQL, at-rest crypto optional). Add a short note, in the project's docs voice, that at-rest crypto is opt-in on every persistent backend, and that a networked backend built without it emits a `PIIGhostSecurityWarning` pointing here. Follow the piighost-docs skill (define by mechanism, no em dash, no mid-sentence colon, `.placeholder` / `.pii` tags where relevant).

- [ ] **Step 2: Mirror in FR**

Apply the byte-identical structure to `docs/fr/security.md`, translating the prose only. Keep code identifiers in English.

- [ ] **Step 3: Build both sites**

Run: `uv run zensical build --clean` and `uv run zensical build -f zensical.fr.toml`
Expected: both build with no error.

- [ ] **Step 4: Commit**

```bash
git add docs/en/security.md docs/fr/security.md
git commit -m "docs(security): document the SQL backend and optional at-rest crypto"
```

---

## Task 7: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Lint gate**

Run: `make lint`
Expected: ruff format --check, ruff check, pyrefly, and bandit all pass.
If pyrefly flags a guarded SQLAlchemy import in the config `build()`, keep the import inside the method (lazy) as written.

- [ ] **Step 2: Full test suite**

Run: `uv run pytest -q`
Expected: all pass, no new skips beyond the integration marker.

- [ ] **Step 3: Optional-dependency guard**

Run: `uv run pytest tests/test_optional_dependencies.py -q`
Expected: PASS — the guarded `sqlalchemy_backend` module is auto-covered (its ImportError names `piighost[sqlalchemy]`).

- [ ] **Step 4: Commit any lint fixes**

```bash
git add -A
git commit -m "chore: satisfy lint after the SQLAlchemy memory backend"
```

(Skip if the working tree is already clean.)

---

## Notes for the implementer

- **DRY**: `warn_plaintext` (Task 1) is the single source for the warning; both backends call it. The digest-and-encrypt helpers are per-backend by design, since Redis stores one blob per message while the SQL backend uses columns.
- **YAGNI**: no TTL, no Alembic, no cross-thread cache in this plan — all deferred in the spec.
- **Crypto is all-or-nothing** everywhere: exactly one of hasher/cipher raises `ValueError`.
- **The engine is injected**; the caller disposes it. `build()` never runs `create_schema()`; the app runs it once at startup.
- Confirm the concrete hasher export name in `src/piighost/crypto/hasher/__init__.py` before writing the hasher-using tests (the plan assumes `HmacHasher`).
