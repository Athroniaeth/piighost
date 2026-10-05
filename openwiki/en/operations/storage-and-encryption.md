---
type: operations
title: Store conversations and protect traces
description: Where piighost keeps the memory of each conversation (in process, Redis, SQL database), how to encrypt this storage, what erasing a conversation really deletes, and how to keep OpenTelemetry traces free of personal data.
tags: [conversation-memory, redis, sqlalchemy, encryption, hashing, observation, opentelemetry, erasure]
sources:
  - id: openwiki-source-884a2e563fa6c83993666a78
    resource: repo://src/piighost/config/models/memory.py
  - id: openwiki-source-beb42dcd927067e197327036
    resource: repo://src/piighost/conversation_memory/base.py
  - id: openwiki-source-19f6f6edbb7533ba166dd534
    resource: repo://src/piighost/conversation_memory/memory.py
  - id: openwiki-source-32946ba53121de4a935726de
    resource: repo://src/piighost/conversation_memory/redis_backend.py
  - id: openwiki-source-193d64415b599d0fdb371fa1
    resource: repo://src/piighost/conversation_memory/sqlalchemy_backend.py
  - id: openwiki-source-c10b33bddc7cace9a0f2a3d4
    resource: repo://src/piighost/crypto/cipher/aesgcm.py
  - id: openwiki-source-48c4068b03eac61e74ad885e
    resource: repo://src/piighost/crypto/hasher/argon2id.py
  - id: openwiki-source-99e6f9e034c36653e9d7ed97
    resource: repo://src/piighost/crypto/hasher/base.py
  - id: openwiki-source-de8939b13acb1ab2a99cd229
    resource: repo://src/piighost/crypto/hasher/sha256.py
  - id: openwiki-source-53ef27c248d6c400169169a3
    resource: repo://src/piighost/observation/__init__.py
  - id: openwiki-source-5ddce4dd4539293afb49cdfd
    resource: repo://src/piighost/pipeline/base.py
  - id: openwiki-source-07566b3f03a831d37fa4fbce
    resource: repo://src/piighost/pipeline/thread.py
  - id: openwiki-source-c23087b7f2444e82c0c323e1
    resource: repo://tests/conversation_memory/test_redis.py
generated: { by: "claude-code", at: "2026-10-02T18:00:00.000Z" }
---

# Store conversations and protect traces

## In short

- To make the reply readable, `piighost` keeps, for each conversation, the sensitive values found in each message. This storage therefore contains personal data.
- The three storage locations are the program memory (lost on restart), Redis and a SQL database.
- Redis and the SQL database can encrypt what they keep. Encryption requires two secrets supplied by the server's environment.
- Erasing a conversation deletes its storage. On a server with several processes, a temporary copy can survive in the other processes as long as no lifetime is set.
- Technical traces contain the clear text by default. A setting replaces it with placeholders.

This page is mainly for developers and operators. The flow of a conversation is described in [Follow a conversation and restore the reply](../processes/follow-a-conversation.md). The terms are defined in the [glossary](../glossary.md). Going to production is described in the technical guide. [Deploy a pipeline in production](../../../docs/en/deployment.md) covers one server, and [Multi-instance deployment](../../../docs/en/multi-instance.md) covers several instances behind a load balancer. The storage guarantees are detailed there in [Security](../../../docs/en/security.md).

## Choose a storage

| Storage | `[memory] type` key | Survives restart | Shared between processes | Lifetime |
|---|---|---|---|---|
| Program memory | `in_memory` | no | no | `ttl` per conversation, `max_threads` (10,000 conversations and one day by default) |
| Redis | `redis` | yes | yes | `ttl` per message |
| SQL database (SQLAlchemy) | `sqlalchemy` | yes | yes | none |

Recommendation: `in_memory` for development and tests, Redis or SQL as soon as several processes serve the same conversation.

### What is stored

Each message is stored with its digest, that is a short string computed from its text, used to recognize the message without keeping that text. The storage also keeps the role of its author (`user` or `assistant`) and its detections (position, text, label, confidence). The text of the detections is the sensitive data.

- Redis: `{namespace}:{thread_id}:msg:{digest}` holds the role and the detections. `{namespace}:{thread_id}:index` holds the arrival order of the messages (`conversation_memory/redis_backend.py:7-12`).
- SQL: one row per message in `piighost_conversation_messages` (`id`, `thread_id`, `message_digest`, `role`, `detections`, `detection_count`).

Encrypting a storage relies on two components, always configured together:

- The hasher: it computes the digest of each message with a secret, the pepper (`PIIGHOST_HASH_PEPPER`). Without the pepper, nobody can recompute the digest of a known text to check whether it was stored.
- The cipher: it encrypts the stored detections with an AES key (`PIIGHOST_CIPHER_KEY`). Without the key, the stored values are unreadable.

## Rules to know

**BR-STO-01.** When you supply a hasher without a cipher, or a cipher without a hasher, then the build fails. In code, the error is `ValueError("Provide both a hasher and a cipher, or neither")`. In configuration, it is `ConfigError("Configure both a hasher and a cipher, or neither")`. Hashing the keys while leaving the values in clear protects nothing.

**BR-STO-02.** When Redis or a SQL database is built without encryption, then a `PIIGhostSecurityWarning` is emitted. A SQLite database is the exception and does not trigger the warning (`conversation_memory/sqlalchemy_backend.py:99-100`).

**BR-STO-03.** When encryption is active, then the conversation identifier stays in clear. It serves as the Redis key prefix and as a SQL column, so that a conversation can be listed and erased. Do not put personal data in it (an e-mail address, a name).

**BR-STO-04.** When the program memory is created without settings, then it keeps at most 10,000 conversations. Beyond that, the least recently used one is evicted. Each conversation expires one day (86,400 seconds) after its last write, and it is dropped at the next access. `max_threads` and `ttl` change these bounds. For example, a conversation written on October 2, 2026 at 9:00 and not touched afterwards is forgotten from October 3, 2026 at 9:00.

**BR-STO-05.** When Redis has a `ttl`, then each message expires this number of seconds after its write. The conversation index receives the same lifetime at each new message. The SQL database has no expiration. Erase the conversations yourself.

**BR-STO-06.** When a conversation is erased, then its storage and the placeholder cache of the process that receives the request are emptied. The other processes keep their cache until its eviction (256 maps at most) or until `token_memo_ttl`. For example, on a server with 4 processes, an erasure request received by process 1 leaves the values in the cache of processes 2 to 4 as long as `token_memo_ttl` is not set.

**BR-STO-07.** When the encryption key is not 16, 24 or 32 bytes once decoded from base64, then the build fails with `InvalidKeyLengthError`.

**BR-STO-08.** When no trace redactor is configured and an OpenTelemetry exporter is active, then the traces carry the clear text. A `PIIGhostSecurityWarning` is emitted at build time, unless `trace_clear_text=True` acknowledges it.

## Configure encrypted Redis

1. Install the extras: `uv add "piighost[redis,crypto,argon2,config]"`.
2. Export the pepper: `PIIGHOST_HASH_PEPPER` (any non-empty string, kept out of the repository).
3. Export the key: `PIIGHOST_CIPHER_KEY="$(openssl rand -base64 32)"`.
4. Start from `examples/config/thread_redis.toml`, which already declares `[memory.hasher]` and `[memory.cipher]`. The memory section has this shape:

```toml
[memory]
type = "redis"
url = "redis://localhost:6379/0"
ttl = 86400

[memory.hasher]
type = "argon2"

[memory.cipher]
type = "aesgcm"
```

5. Load the pipeline with `load_thread_pipeline("pipeline.toml")`.

For a SQL database, replace the section with `type = "sqlalchemy"`, export the asynchronous URL in `PIIGHOST_DATABASE_URL`, then call `await pipeline.memory.create_schema()` once at startup. Loading the configuration does not create the table.

### Check

```bash
redis-cli --scan --pattern 'piighost:*'
```

You must see `piighost:<thread_id>:msg:<digest>` keys. `redis-cli GET` on one of them must return unreadable bytes, not a JSON containing the values.

## Choose the hasher

| Hasher | `type` | Cost | Resists a pepper leak |
|---|---|---|---|
| HMAC-SHA256 | `sha256` | fast | no |
| Argon2id | `argon2` | slow, memory-hungry | yes, partly |

Argon2id takes by default `time_cost = 2`, `memory_cost = 19456` KiB, `parallelism = 1`, `hash_length = 32`. The hasher runs at each message, so measure the latency before hardening these values.

## Redact the traces

The pipeline opens one span per stage (`piighost.detect`, `piighost.link`, `piighost.render`, etc.) through OpenTelemetry. A span is a trace entry that measures one stage and carries its data. Without the `observation` extra, the tracer does nothing. With it, the spans go to the application's `TracerProvider`.

- Without a redactor, the text and the detected values are traced in clear. The traces then contain personal data. Keep this mode for a trace service you control, and acknowledge it with `trace_clear_text=True` (BR-STO-08).
- With `observation_redactor` (a placeholder factory, `[observation_redactor]` section), the values are replaced with placeholders in the traces.
- The conversation pipeline sets the conversation identifier in the `langfuse.session.id` attribute, in clear, even with a redactor.

## Pitfalls

- **The placeholder cache is not shared** between processes. Set `token_memo_ttl` as soon as you erase conversations on a multi-process deployment (BR-STO-06).
- **The SQL table is not created by the configuration.** Without `create_schema()`, the first message fails.
- **Two simultaneous SQL writes of the same message** can raise a uniqueness constraint error, because the check and then the write are not atomic (`sqlalchemy_backend.py:124-127`). Redis, for its part, retries under `WATCH`.
- **The word pattern cache** is shared by the whole process. `forget_thread` does not empty it. Call `clear_boundary_cache` if the erasure request covers the whole process.
- **A lost AES key makes the memory unreadable.** The ongoing conversations can no longer be restored.

> [!WARNING]
> Changing `PIIGHOST_HASH_PEPPER` or `PIIGHOST_CIPHER_KEY` on an existing storage makes the already stored conversations unfindable or undecryptable. Empty the storage or plan a migration before changing a secret.

## Where the rules live

| Rule | Location |
|---|---|
| BR-STO-01 | `conversation_memory/base.py:59-71` (`require_paired_crypto`), `config/models/memory.py:61` (the same rejection in configuration) |
| BR-STO-02 | `conversation_memory/base.py:43` (`warn_plaintext`), called by `conversation_memory/redis_backend.py:105` and `conversation_memory/sqlalchemy_backend.py:99-100`, which spares SQLite |
| BR-STO-03 | `conversation_memory/redis_backend.py:107-113` (`_index_key`, keys prefixed by the conversation identifier), `conversation_memory/sqlalchemy_backend.py:92` (`thread_id` column) |
| BR-STO-04 | `conversation_memory/memory.py:45-62` (`__init__`, bounds `DEFAULT_MAX_THREADS` and `DEFAULT_TTL` at lines 13 and 20), `_expired` lines 140-144, `_evict` lines 150-157 |
| BR-STO-05 | `conversation_memory/redis_backend.py:148-152` (`remember`, expiration of the message and of the index) |
| BR-STO-06 | `pipeline/thread.py:244-262` (`forget_thread`), `pipeline/thread.py:29` (`_TOKEN_MEMO_MAX = 256`) |
| BR-STO-07 | `crypto/cipher/aesgcm.py:46-52` (`AesGcmCipher.__init__`) |
| BR-STO-08 | `pipeline/base.py:190-202` (the warning of `__init__`, acknowledged by `trace_clear_text`) |

## Tests

| Test | Covers |
|---|---|
| `tests/conversation_memory/` | Each storage: conversation isolation, erasure, lifetimes, clear-text warning (`test_warn_plaintext.py`) |
| `tests/conversation_memory/test_sqlalchemy.py` | Table creation, encrypted storage in SQL |
| `tests/crypto/` | AES key length, empty pepper rejected, determinism of the hashers |
| `tests/observation/` | Emitted spans, redaction of their content, clear-text trace warning |

The Redis tests run against `fakeredis` (`tests/conversation_memory/test_redis.py:21-27`), not against a real server. `test_concurrent_identical_remembers_do_not_duplicate` checks atomicity under `WATCH` with this fake client. The behavior of a real Redis cluster is not covered.

See also [Configure a pipeline](configuration-and-catalog.md) for the secrets and the `[memory]` section.
