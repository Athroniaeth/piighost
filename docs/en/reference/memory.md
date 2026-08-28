---
icon: lucide/database
tags:
  - Memory
---

# Conversation memory reference

Module: `piighost.conversation_memory`

A conversation memory stores, per thread, the detections found in each message. A `ThreadAnonymizationPipeline` reads that store to keep one placeholder per value across a whole conversation: a name seen early reads as the same token later, on any turn. Every backend satisfies the `AnyConversationMemory` port, so the pipeline treats an in-process dict and a shared database the same way.

```python
from piighost.conversation_memory import (
    InMemoryConversationMemory,
    RedisConversationMemory,
    SqlAlchemyConversationMemory,
)
```

`RedisConversationMemory` and `SqlAlchemyConversationMemory` are exposed lazily: importing one without its extra installed raises `ImportError` with the install command.

## The `AnyConversationMemory` port

Four async methods make up the interface. A backend implements all four, whatever it stores them in.

| Method | Purpose |
|--------|---------|
| `remember(thread_id, message, detections, role=MessageRole.USER)` | Cache the detections found in a message, replacing any prior entry. |
| `get_detections(thread_id, message=None)` | Return a thread's detections for one message, or the whole thread as a first-seen-order union when `message` is omitted. |
| `get_provenance(thread_id)` | Return, per value, the role of its first occurrence in the thread (casefolded value → `MessageRole`). |
| `forget(thread_id)` | Erase a thread and report a `Forgotten` count of the messages and detections dropped. |

The pipeline drives these for you. You call the memory directly only to pre-seed or inspect a thread, and `create_schema()` on the SQL backend at startup.

## `InMemoryConversationMemory`

```python
InMemoryConversationMemory()
```

A process-local per-thread cache in a dict. It suits development, tests, and single-process deployments. Nothing survives a restart and nothing is shared across workers, so behind a load balancer two workers number the same value differently. It needs no optional extra and is the default when a `ThreadAnonymizationPipeline` is built without a memory.

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

A persistent, multi-worker store. Every worker pointed at the same Redis reads the same numbering, so tokens stay consistent behind a load balancer. `namespace` prefixes every key, and `ttl` is the seconds a message lives before eviction, or omitted to keep it until Redis drops it. Requires `piighost[redis]`.

Pass both a `hasher` and a `cipher` to store securely (the key is hashed under a pepper, the value encrypted), or neither to store in clear. Passing exactly one raises `ValueError`, and a plaintext setup on a networked store emits a `PIIGhostSecurityWarning`.

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

The `[memory]` section of a config file builds any of these, discriminated on `type` (`in_memory`, `redis`, `sqlalchemy`). Its keys, the hasher and cipher options, and the environment variables for secrets are in the [configuration reference](../configuration/toml.md).

## See also

- [Configuration reference](../configuration/toml.md): every `[memory]` key, TOML and JSON.
- [Multi-instance deployment](../multi-instance.md): why a shared backend is required behind a load balancer.
- [Deploy a production pipeline](../deployment.md): the full Redis and SQL setup with secrets.
- [Security](../security.md): the at-rest guarantees and the backend comparison.
