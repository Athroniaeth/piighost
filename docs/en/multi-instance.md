---
icon: lucide/network
seo_title: Run PII de-identification on several workers with Redis
description: Workers behind a load balancer number the same value differently. Share the conversation memory in Redis so every worker gives it the same placeholder.
---

# Multi-instance deployment

A thread pipeline keeps one placeholder per value for the length of a conversation, so a name seen early reads as the same token later. That consistency depends on where the conversation memory lives. The default `InMemoryConversationMemory` is process-local. So two workers behind a load balancer number the same value differently mid-conversation. A shared Redis memory fixes it.

## Why one process is not enough

`InMemoryConversationMemory` keeps each thread's detections in a dictionary that lives in one process. It suits development, tests, and a single-process deployment. Nothing survives a restart and nothing is shared across processes. It is bounded by default, and `max_threads` and `ttl` adjust its growth. A multi-worker deployment still needs a shared backend.

The problem appears the moment a load balancer routes the same `thread_id` to more than one worker. Each worker holds its own memory, and these memories do not talk to each other. A value tokenized as `<<PERSON:1>>`{ .placeholder } on worker A is unknown to worker B, which numbers from scratch.

```text
Turn 1, routed to worker A: "Patrick called."
  worker A memory: { Patrick -> <<PERSON:1>> }
  worker B memory: {}

Turn 2, routed to worker B: "Marie called back."
  worker A memory: { Patrick -> <<PERSON:1>> }
  worker B memory: { Marie -> <<PERSON:1>> }

Turn 3, routed to worker A: "Patrick and Marie met."
  worker A memory: { Patrick -> <<PERSON:1>>, Marie -> <<PERSON:2>> }
  worker B memory: { Marie -> <<PERSON:1>> }
```

The LLM receives `<<PERSON:1>>`{ .placeholder } for `Patrick`{ .pii } on turn 1, then for `Marie`{ .pii } on turn 2. On turn 3, `Marie`{ .pii } becomes `<<PERSON:2>>`{ .placeholder }. The same token names two people, and the same person wears two tokens.

The failure is silent. No exception is raised, and the pipeline produces valid tokenized text. The inconsistency only shows in the LLM's answers. The LLM loses the thread between turns, because the tokens no longer name the same people.

## Configure a shared Redis memory

Point every worker at one Redis instance. The tokens are assigned over the union of a thread's detections. That union lives in Redis, so every worker reads the same numbering. The `thread_id` stays the unit of isolation, so two users never share a token.

```toml title="pipeline.toml"
--8<-- "snippets/redis_pipeline.toml"
```

```python
--8<-- "snippets/redis_load.py:example"
```

With Redis, turn 2 goes differently. Worker B reads the memory worker A wrote on turn 1. `<<PERSON:1>>`{ .placeholder } is already given to `Patrick`{ .pii } there, so `Marie`{ .pii } receives `<<PERSON:2>>`{ .placeholder }. Any worker that picks up the conversation reproduces the same token for the same value.

## Check that the workers agree

Build two pipelines from the same file, one per worker, and send one thread to each. Each pipeline keeps its own process cache. So only the shared Redis can make the second pipeline reuse the first one's tokens.

```python
--8<-- "snippets/redis_two_workers.py:example"
```

The output should be:

```text
--8<-- "snippets/redis_two_workers.out"
```

`bob@corp.com`{ .pii }, new to the thread, takes `<<EMAIL:2>>`{ .placeholder }. `alice@corp.com`{ .pii } keeps the `<<EMAIL:1>>`{ .placeholder } worker A gave it. Without the shared memory, worker B would number its message from scratch and give `<<EMAIL:1>>`{ .placeholder } to Bob. In production, run the same check against two worker processes behind the load balancer.

The Redis backend can encrypt each stored value and hash each key. That protection is opt-in and all-or-nothing. The config shown above sets both a hasher and a cipher, so it gets that protection. It reads its pepper and cipher key from the environment. Those secrets and the full setup are covered in [Deployment](deployment.md). Every `[memory]` key is in the [configuration reference](configuration/toml.md).

A SQL database is the other shared store. `type = "sqlalchemy"` gives the same cross-worker consistency backed by PostgreSQL (or any async SQLAlchemy driver). This backend suits a stack that already runs a relational database and wants the token mapping to survive restarts durably. It reads the database URL from `PIIGHOST_DATABASE_URL` and takes the same optional hasher and cipher as Redis.

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

A shared memory settles the numbering. But each worker also memoizes the token map it derives, meaning it keeps that map in a local cache, the memo. The memo is keyed on the thread state the worker read. It holds the thread's values in clear, and `forget_thread` only reaches the memo of the process it runs in. So an erasure request routed to worker A leaves worker B's copy standing until its size bound evicts it.

Nothing stale is ever served, because the memo key carries the union read from the store. The erasure emptied that union, so worker B recomputes and finds nothing. The issue is retention, not correctness. `token_memo_ttl` bounds that retention without any cross-worker message, so there is no message to lose:

```toml
token_memo_ttl = 300.0

[memory]
type = "redis"
url = "redis://localhost:6379/0"
```

It is a top-level scalar, so it goes above the first section. Five minutes is a reasonable starting point, long enough that a live conversation keeps hitting the memo, short enough that a forgotten thread's values do not linger.

The sweep rides on the traffic of the worker it runs in, not on a timer. An entry is dropped the next time that worker derives a token map. A worker that goes idle right after an erasure therefore keeps its copy until it serves another request, or until the process ends. Bounding that case would take a background task, and a library has no business starting one. So the ttl is a bound on busy workers, and the process lifetime is the bound on idle ones. If the ttl is unset, an entry stays until 256 others push it out. On a quiet worker, that eviction can take a long time.

## Align with LangGraph

The same trap hits LangGraph's `checkpointer`. `MemorySaver` is process-local, `PostgresSaver` and `RedisSaver` are shared. If your agent already runs a shared saver behind the load balancer, run the `piighost` memory on the same infrastructure. Then, on any worker, a `thread_id` that has a checkpointed state can also reach its token mapping.

## See also

- [Deployment](deployment.md): the full Redis setup, extras, and secrets.
- [Configuration reference](configuration/toml.md): every `[memory]` key, TOML and JSON.
- [Security](security.md): the at-rest guarantees of the Redis backend and the backend comparison.
- [Conversational pipeline](getting-started/conversation.md): how tokens stay consistent across a thread.
- [Store conversations and protect traces](../../openwiki/en/operations/storage-and-encryption.md): the storage rules, `BR-STO-01` to `BR-STO-08`, written for a DPO or an operator.
