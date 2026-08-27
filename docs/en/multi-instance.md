---
icon: lucide/network
---

# Multi-instance deployment

A thread pipeline keeps one placeholder per value for the length of a conversation, so a name seen early reads as the same token later. That consistency depends on where the conversation memory lives. The default `InMemoryConversationMemory` is process-local, so two workers behind a load balancer number the same value differently mid-conversation. A shared Redis memory fixes it.

!!! note "Summary"
    `InMemoryConversationMemory` holds each thread's detections in a process dictionary. Behind a load balancer, the same `thread_id` routed to two workers will see `Patrick`{ .pii } tokenized as `<<PERSON:1>>`{ .placeholder } on one worker and `<<PERSON:2>>`{ .placeholder } on the other, and the LLM can no longer relate the two. The fix is `RedisConversationMemory`, shared by every worker.

## Why one process is not enough

`InMemoryConversationMemory` keeps each thread's detections in a dictionary that lives in one process. It suits development, tests, and a single-process deployment. Nothing survives a restart and nothing is shared across processes.

The problem appears the moment a load balancer routes the same `thread_id` to more than one worker. Each worker holds its own memory, and these memories do not talk to each other. A value tokenized as `<<PERSON:1>>`{ .placeholder } on worker A is unknown to worker B, which numbers it fresh.

```text
Turn 1 (routed to worker A)
  worker A memory: { Patrick -> <<PERSON:1>> }
  worker B memory: {}

Turn 2 (routed to worker B, "Patrick" still in the context)
  worker B memory: { Patrick -> <<PERSON:1>> }   # numbered fresh, may collide

Turn 3 (worker B sees "Marie")
  worker B memory: { Patrick -> <<PERSON:1>>, Marie -> <<PERSON:2>> }

Turn 4 (worker A sees "Marie", numbers from its own state)
  worker A memory: { Patrick -> <<PERSON:1>>, Marie -> <<PERSON:2>> }
  # Marie could have taken another number if a different PII had preceded it on A.
```

The failure is silent. No exception is raised, the pipeline produces valid tokenized text, and the inconsistency only shows in the LLM's answers, which lose the thread between turns because the same person now wears two names.

## Configure a shared Redis memory

Point every worker at one Redis instance. The tokens are assigned over the union of a thread's detections, and that union lives in Redis, so every worker reads the same numbering. The `thread_id` stays the unit of isolation, so two users never share a token.

```toml title="pipeline.toml"
[detector]
type = "regex"
catalogs = ["generic"]

[linker]
type = "exact"

[anonymizer.placeholder]
type = "label_counter"

[memory]
type = "redis"
url = "redis://redis.internal:6379/0"
namespace = "piighost"
ttl = 3600

[memory.hasher]
type = "argon2"

[memory.cipher]
type = "aesgcm"
```

```python
from piighost.config import load_thread_pipeline

pipeline = load_thread_pipeline("pipeline.toml")
```

Now the turn-2 case resolves the other way: worker B reads `Patrick -> <<PERSON:1>>`{ .placeholder } straight from Redis and keeps it, because the store worker A wrote to is the store worker B reads from. Any worker that picks up the conversation reproduces the same token for the same value.

The Redis memory also encrypts each stored value and hashes each key, and reads its pepper and cipher key from the environment. Those secrets and the full setup are covered in [Deploy a production pipeline](deployment.md), and every `[memory]` key is in the [configuration reference](configuration/toml.md).

A SQL database is the other shared store. `type = "sqlalchemy"` gives the same cross-worker consistency backed by PostgreSQL (or any async SQLAlchemy driver), which suits a stack that already runs a relational database and wants the token mapping to survive restarts durably. It reads the database URL from `PIIGHOST_DATABASE_URL` and takes the same optional hasher and cipher as Redis.

```toml
[memory]
type = "sqlalchemy"
url_env = "PIIGHOST_DATABASE_URL"

[memory.hasher]
type = "argon2"

[memory.cipher]
type = "aesgcm"
```

## Align with LangGraph

The same trap hits LangGraph's `checkpointer`. `MemorySaver` is process-local, `PostgresSaver` and `RedisSaver` are shared. If your agent already runs a shared saver behind the load balancer, run the `piighost` memory on the same infrastructure. A `thread_id` that has a checkpointed state then also has its token mapping reachable, on any worker.

## See also

- [Deploy a production pipeline](deployment.md): the full Redis setup, extras, and secrets.
- [Configuration reference](configuration/toml.md): every `[memory]` key, TOML and JSON.
- [Security](security.md): the at-rest guarantees of the Redis backend and the backend comparison.
- [Conversational pipeline](getting-started/conversation.md): how tokens stay consistent across a thread.
