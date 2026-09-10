---
icon: lucide/network
---

# Multi-instance deployment

A thread pipeline keeps one placeholder per value for the length of a conversation, so a name seen early reads as the same token later. That consistency depends on where the conversation memory lives. The default `InMemoryConversationMemory` is process-local, so two workers behind a load balancer number the same value differently mid-conversation. A shared Redis memory fixes it.

!!! note "Summary"
    `InMemoryConversationMemory` holds each thread's detections in a process dictionary. Behind a load balancer, the same `thread_id` routed to two workers will see `Patrick`{ .pii } tokenized as `<<PERSON:1>>`{ .placeholder } on one worker and `<<PERSON:2>>`{ .placeholder } on the other, and the LLM can no longer relate the two. The fix is `RedisConversationMemory`, shared by every worker.

## Why one process is not enough

`InMemoryConversationMemory` keeps each thread's detections in a dictionary that lives in one process. It suits development, tests, and a single-process deployment. Nothing survives a restart and nothing is shared across processes. It can be bounded with `max_threads` and `ttl` to cap its growth, though a multi-worker deployment still needs a shared backend.

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

Now the turn-2 case resolves the other way, worker B reads `Patrick -> <<PERSON:1>>`{ .placeholder } straight from Redis and keeps it, because the store worker A wrote to is the store worker B reads from. Any worker that picks up the conversation reproduces the same token for the same value.

The Redis backend can encrypt each stored value and hash each key. That protection is opt-in and all-or-nothing, so the config shown above, which sets both a hasher and a cipher, gets it, reading its pepper and cipher key from the environment. Those secrets and the full setup are covered in [Deploy a production pipeline](deployment.md), and every `[memory]` key is in the [configuration reference](configuration/toml.md).

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

## Bound the token memo on every worker

A shared memory settles the numbering, but each worker also memoizes the token map it derives, keyed on the thread state it read. That memo holds the thread's values in clear, and `forget_thread` only reaches the memo of the process it runs in. So an erasure request routed to worker A leaves worker B's copy standing until its size bound evicts it.

Nothing stale is ever served: the memo key carries the union read from the store, which the erasure emptied, so worker B recomputes and finds nothing. The issue is retention, not correctness. `token_memo_ttl` bounds it without any cross-worker message to lose:

```toml
token_memo_ttl = 300.0

[memory]
type = "redis"
url = "redis://localhost:6379/0"
```

It is a top-level scalar, so it goes above the first section. Five minutes is a reasonable starting point, long enough that a live conversation keeps hitting the memo, short enough that a forgotten thread's values do not linger.

The sweep rides on the traffic of the worker it runs in: an entry is dropped the next time that worker derives a token map, not on a timer. A worker that goes idle right after an erasure therefore keeps its copy until it serves another request, or until the process ends. Bounding that would take a background task, which a library has no business starting, so the ttl is a bound on busy workers and the process lifetime is the bound on idle ones. Leaving the ttl unset keeps an entry until 256 others push it out, which on a quiet worker can be a long time.

## Align with LangGraph

The same trap hits LangGraph's `checkpointer`. `MemorySaver` is process-local, `PostgresSaver` and `RedisSaver` are shared. If your agent already runs a shared saver behind the load balancer, run the `piighost` memory on the same infrastructure. A `thread_id` that has a checkpointed state then also has its token mapping reachable, on any worker.

## See also

- [Deploy a production pipeline](deployment.md): the full Redis setup, extras, and secrets.
- [Configuration reference](configuration/toml.md): every `[memory]` key, TOML and JSON.
- [Security](security.md): the at-rest guarantees of the Redis backend and the backend comparison.
- [Conversational pipeline](getting-started/conversation.md): how tokens stay consistent across a thread.
