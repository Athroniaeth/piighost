---
icon: lucide/database
tags:
  - Memory
---

# Conversation memory reference

Module: `piighost.conversation_memory`

A conversation memory stores, per thread, the detections found in each message. A `ThreadAnonymizationPipeline` reads that store to keep one placeholder per value across a whole conversation. A name seen early thus gets the same token later, on any turn. Every backend satisfies the `AnyConversationMemory` port, so the pipeline treats an in-process dict and a shared database the same way.

```python
from piighost.conversation_memory import (
    InMemoryConversationMemory,
    RedisConversationMemory,
    SqlAlchemyConversationMemory,
)
```

`RedisConversationMemory` and `SqlAlchemyConversationMemory` are exposed lazily, that is imported only on first access. Importing one without its extra installed raises `ImportError`, with the install command in the message.

## The `AnyConversationMemory` port

Four async methods make up the interface. A backend implements all four, whatever it stores them in.

| Method | Purpose |
|--------|---------|
| `remember(thread_id, message, detections, role=MessageRole.USER)` | Cache the detections found in a message, replacing any prior entry. |
| `get_detections(thread_id, message=None)` | Return a thread's detections for one message. When `message` is omitted, return those of the whole thread, merged in first-seen order. |
| `get_provenance(thread_id)` | Return, per value, the role of its first occurrence in the thread (value key → `MessageRole`). The value key ignores spaces and case. |
| `forget(thread_id)` | Erase a thread and report a `Forgotten` count of the messages and detections dropped. |

The pipeline drives these for you. You call the memory directly in two cases only, to pre-seed or inspect a thread, and to call `create_schema()` on the SQL backend at startup.

### `Forgotten`

```python
@dataclass(frozen=True, slots=True)
class Forgotten:
    messages: int
    detections: int
```

`Forgotten` describes what `forget` erased. It serves as evidence for a right-to-erasure request. `forget_thread` on a thread pipeline returns the same object.

| Field | Type | Meaning |
|-------|------|---------|
| `messages` | `int` | How many cached messages were dropped |
| `detections` | `int` | How many detections across those messages were dropped |

## `InMemoryConversationMemory`

```python
InMemoryConversationMemory(
    max_threads: int | None = 10_000,
    ttl: float | None = 86_400.0,
    time_source: Callable[[], float] = time.monotonic,
)
```

A process-local per-thread cache in a dict. It suits development, tests, and single-process deployments. Nothing survives a restart and nothing is shared across workers. Behind a load balancer, two workers therefore number the same value differently. It needs no optional extra. It is the default memory when a `ThreadAnonymizationPipeline` is built without a memory.

The store is bounded by default, to 10,000 threads (`DEFAULT_MAX_THREADS`) and one day idle (`DEFAULT_TTL`). `max_threads` evicts the least-recently-used thread. `ttl` expires an idle thread. The expiry happens on the next access to that thread, after which its tokens are no longer restored. Passing `None` lifts the matching bound. The store then grows until `forget_thread` is called. `time_source` is the clock `ttl` reads, injectable for tests.

## `RedisConversationMemory`

```python
RedisConversationMemory(
    client: Redis,
    hasher: AnyHasher | None = None,
    cipher: AnyCipher | None = None,
    namespace: str = "piighost",
    ttl: int | None = None,
)
```

A persistent, multi-worker store. Every worker pointed at the same Redis reads the same numbering, so tokens stay consistent behind a load balancer. `namespace` prefixes every key. `ttl` is the number of seconds a message lives before eviction. Omit it to keep the message until Redis drops it. Requires `piighost[redis]`.

Pass both a `hasher` and a `cipher` to store securely (the key is hashed under a pepper, the value encrypted), or neither to store in clear. Passing exactly one raises `ValueError`. A plaintext setup on a networked store emits a `PIIGhostSecurityWarning`.

## `SqlAlchemyConversationMemory`

```python
SqlAlchemyConversationMemory(
    engine: AsyncEngine,
    hasher: AnyHasher | None = None,
    cipher: AnyCipher | None = None,
    table_name: str = "piighost_conversation_messages",
)
```

A durable, multi-worker store over any async SQLAlchemy driver (PostgreSQL via `asyncpg`, SQLite via `aiosqlite`, ...). It takes an injected `AsyncEngine` whose lifecycle you own. Call `await memory.create_schema()` once at startup to create the table idempotently. The `hasher`/`cipher` follow the same all-or-nothing rule as Redis. Requires `piighost[sqlalchemy]`.

## Building from a file

The `[memory]` section of a config file builds any of these backends. Its `type` field picks which one (`in_memory`, `redis`, `sqlalchemy`). Its keys, the hasher and cipher options, and the environment variables for secrets are in the [configuration reference](../configuration/toml.md).

## See also

- [Configuration reference](../configuration/toml.md): every `[memory]` key, TOML and JSON.
- [Multi-instance deployment](../multi-instance.md): why a shared backend is required behind a load balancer.
- [Deploy a production pipeline](../deployment.md): the full Redis and SQL setup with secrets.
- [Security](../security.md): the at-rest guarantees and the backend comparison.
