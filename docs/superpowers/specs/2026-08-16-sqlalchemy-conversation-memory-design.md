# SQLAlchemy conversation memory + optional at-rest crypto — Design

**Goal:** Add `SqlAlchemyConversationMemory`, a durable `AnyConversationMemory`
backend on async SQLAlchemy 2.0 for long-lived conversations, and make at-rest
encryption optional across every persistent backend (retrofitting Redis), with a
security warning when a networked backend runs without crypto.

**Architecture:** A third backend beside `InMemoryConversationMemory` and
`RedisConversationMemory`, satisfying the same `AnyConversationMemory` port, over
an injected async SQLAlchemy engine. At-rest crypto (a hasher for the message
key, a cipher for the detections) becomes opt-in everywhere; when it is absent on
a networked backend the constructor emits a `PIIGhostSecurityWarning` pointing at
the security doc page.

**Tech stack:** SQLAlchemy 2.0 (async), aiosqlite (dev + tests), asyncpg
(PostgreSQL, prod). Reuses the existing `AnyHasher` / `AnyCipher` crypto ports
and the config layer.

---

## Scope

Two cohesive workstreams in one spec:

- **(a) New SQL backend**: `SqlAlchemyConversationMemory` + `SqlAlchemyMemoryConfig`
  + the `sqlalchemy` extra + tests + docs.
- **(b) Redis retrofit**: make `hasher` / `cipher` optional on
  `RedisConversationMemory` and `RedisMemoryConfig`, and add the shared
  security warning. This changes a shipped component's default posture, from
  encryption-required to plaintext-allowed-with-warning.

**Out of scope (deliberately):**

- Alembic migrations and a migration CLI. v1 uses `create_schema()`
  (`metadata.create_all`) with a stable MetaData so Alembic can be layered on
  later as its own sub-project. See "Deferred" below.
- The cross-thread result cache (roadmap "Optional result cache"). That is a
  different concern (dedup by text hash across threads) and stays a separate
  roadmap item.
- TTL / automatic expiry. The goal is durability for long conversations, so v1
  keeps data until `forget()` is called. A retention/TTL option can come later.

## Decisions (from brainstorming)

1. Purpose: a durable `AnyConversationMemory` backend (per-thread detections),
   sibling to InMemory/Redis.
2. Crypto: opt-in on every backend. `hasher` and `cipher` optional; both or
   neither (exactly one raises). None means plaintext storage.
3. Warning: on a networked backend (Redis; SQL with a non-sqlite dialect) built
   without crypto, emit `PIIGhostSecurityWarning` referencing the security page.
   InMemory (ephemeral) and sqlite (local dev) do not warn.
4. Databases: sqlite via aiosqlite, PostgreSQL via asyncpg, async SQLAlchemy 2.0.
5. Schema management: `create_schema()` (create_all) in v1; Alembic deferred.
6. Schema shape: relational table with real columns (approach A), injected engine.

## Component and placement

- `SqlAlchemyConversationMemory` in
  `src/piighost/conversation_memory/sqlalchemy_backend.py`, a guarded optional
  module (raises `ImportError` pointing at `piighost[sqlalchemy]` when the
  dependency is missing), exposed lazily through the package `__getattr__`, like
  `redis_backend.py`.
- Constructor:
  `SqlAlchemyConversationMemory(engine: AsyncEngine, hasher: AnyHasher | None = None, cipher: AnyCipher | None = None, table_name: str = "piighost_conversation_messages")`.
  - Crypto is all-or-nothing: passing exactly one of `hasher` / `cipher` raises
    `ValueError`.
  - The engine is injected; the caller owns its lifecycle and disposes it. The
    backend never creates or closes the engine.
- `async def create_schema(self) -> None`: idempotent, runs
  `metadata.create_all` via `engine.begin()` + `conn.run_sync(...)`. Called once
  at application startup.

## Schema

One table, `piighost_conversation_messages` (name from `table_name`):

- `id`: integer, autoincrement, primary key. Gives stable first-seen order
  (order by `id`).
- `thread_id`: string, indexed.
- `message_digest`: string. The security hasher's output if a hasher is set,
  otherwise a plain SHA-256 hex digest. The clear message text is never stored.
- `role`: string, `"user"` or `"assistant"`.
- `detections`: `LargeBinary`. Ciphertext of the detections JSON if a cipher is
  set, otherwise the clear UTF-8 JSON bytes.
- `detection_count`: integer. Lets `forget()` report counts without decrypting.
- `UNIQUE(thread_id, message_digest)` for dedup and upsert.

Detections are serialized as `json([d.to_dict() for d in detections])`, then
encrypted when a cipher is set. The role is a column, not part of the blob.

Upsert is portable (no dialect-specific `ON CONFLICT` in v1): look up the row by
`(thread_id, message_digest)`, then `UPDATE` (role, detections, detection_count)
if present, else `INSERT`. This matches the Redis backend's check-then-set and
preserves the original `id`, so first-seen order survives a rewrite.

## Method mapping (AnyConversationMemory)

- `remember(thread_id, message, detections, role)`: compute the digest, serialize
  and optionally encrypt the detections, then upsert the row.
- `get_detections(thread_id, message=None)`: with a message, select the one row's
  detections (decrypt, parse) or return `None` on a miss; with no message, select
  every row for the thread ordered by `id`, decrypt each, and concatenate into
  one list.
- `get_provenance(thread_id)`: select rows ordered by `id`, decrypt each, and
  build `{value.casefold(): role}` with `setdefault`, so first-seen role wins.
- `forget(thread_id)`: sum `detection_count` and count rows for the thread, then
  `DELETE WHERE thread_id = ...`, and return `Forgotten(messages, detections)`.
  Forgetting an unknown thread drops nothing and reports zero.

## Optional crypto and the security warning

- New warning category `PIIGhostSecurityWarning(UserWarning)` in
  `exceptions.py`.
- Both backends warn at construction when built without crypto on a networked
  store:
  - SQL: warn when `engine.dialect.name != "sqlite"` and no crypto.
  - Redis: always networked, so warn whenever no crypto.
- The warning message names the backend, states that PII is stored in clear, and
  links `https://athroniaeth.github.io/piighost/security/` with the recommendation
  to configure a hasher and cipher.
- Redis retrofit: `RedisConversationMemory.__init__` gets
  `hasher: AnyHasher | None = None, cipher: AnyCipher | None = None`. In plaintext
  mode it stores the clear JSON and keys messages by a plain SHA-256 digest.
  Passing exactly one of hasher/cipher raises `ValueError`, matching the SQL
  backend.

## Configuration

- `SqlAlchemyMemoryConfig` (pydantic) with `build() -> SqlAlchemyConversationMemory`:
  - Reads the database URL from an environment variable whose name is a config
    field, default `PIIGHOST_DATABASE_URL`; raises `ConfigError` when it is unset,
    consistent with the "secrets from the environment only" rule.
  - Builds the `AsyncEngine` from that URL.
  - Reuses the existing optional cipher and hasher config models; passes them to
    the backend, or none for plaintext mode.
  - `build()` does not run `create_schema()`; schema creation is an explicit
    startup step the caller drives, so the config stays side-effect free.
- `RedisMemoryConfig`: the cipher and hasher configs become optional; with
  neither, it builds a plaintext Redis backend (which then warns).

## Extra and dependencies

- New optional extra: `sqlalchemy = ["sqlalchemy[asyncio]>=2.0", "aiosqlite>=0.19", "asyncpg>=0.29"]`.
  Added to the `all` extra and the dev dependency group.
- Guarded import pattern (imports of SQLAlchemy live inside
  `sqlalchemy_backend.py`, raising `ImportError` with `piighost[sqlalchemy]`), so
  the core never imports it eagerly. `tests/test_optional_dependencies.py`
  auto-covers the guarded module.

## Error handling

- Missing dependency: `ImportError` naming `piighost[sqlalchemy]`.
- Exactly one of hasher/cipher: `ValueError` at construction.
- Missing database URL env var at build time: `ConfigError`.
- Networked backend without crypto: `PIIGhostSecurityWarning` (not an error).

## Testing

- Run against `aiosqlite` on a temporary file database (no external service, the
  way the Redis tests use `fakeredis`).
- `TestConformance`: the backend is an `AnyConversationMemory`.
- Round-trips: `remember` then `get_detections` (per message and whole thread),
  `get_provenance` first-seen role, `forget` counts and erasure, unknown-thread
  and unseen-message misses.
- Crypto mode with a hasher and cipher (reuse existing crypto test doubles) and
  plaintext mode.
- The all-or-nothing crypto guard raises `ValueError`.
- The warning fires for a non-sqlite dialect without crypto and stays silent for
  sqlite; assert with `pytest.warns` / `warnings.catch_warnings`.
- Redis retrofit: plaintext round-trip and the warning.

## Documentation (EN + FR, mirrored)

- `security.md`: update the memory-backend comparison to cover the SQL backend,
  optional at-rest crypto, and the warning.
- A section (getting-started or deployment) on wiring the SQL backend, its TOML
  config, and `create_schema()` at startup.
- The roadmap's "Optional result cache" item stays, unchanged, as a distinct
  future concern.

## Deferred: Alembic migrations via CLI

The v1 MetaData is stable and single-table, so Alembic's value does not yet pay
for its cost (packaging the migration env as package data, an async `env.py`, a
CLI wrapper around `alembic.command.upgrade`, and maintainer autogenerate). When
schema evolution becomes a real need, add Alembic as its own sub-project: the
first migration is the current schema as a baseline, generated from the same
MetaData.
