---
icon: lucide/container
---

# Deploy a production pipeline

This guide sets up a thread pipeline for production, with a Redis conversation memory that persists across restarts and workers, encrypts every stored value, and reads its secrets from the environment. If you only need a single process that keeps nothing after it exits, the in-RAM memory is enough and you can skip to [Conversational pipeline](getting-started/conversation.md).

The pipeline reads its shape from a config file, so the deployment carries a TOML file plus a handful of environment variables. No pipeline code is written by hand.

## Install the extras

The Redis memory pulls three extras beyond the config layer, plus one for the Argon2 hasher used below.

```bash
uv add 'piighost[config,redis,crypto,argon2]'
```

The `config` extra reads the file, `redis` talks to the store, `crypto` provides the AES-GCM cipher, and `argon2` provides the Argon2id hasher. Drop `argon2` if you key messages with HMAC-SHA256 instead.

## Write the config file

A `[memory]` section turns the pipeline into a thread pipeline keeping per-thread state. Its `type = "redis"` names the store, `[memory.hasher]` keys each message into its storage key, and `[memory.cipher]` encrypts each stored value.

```toml title="pipeline.toml"
--8<-- "snippets/redis_pipeline.toml"
```

`namespace` prefixes every key so `piighost` shares a Redis instance with other applications without collisions. `ttl` is the seconds a stored message lives before Redis evicts it, or you omit it to keep entries until the store decides to drop them. `label_counter` emits `<<PERSON:1>>`{ .placeholder }, a token that carries identity, which the [middleware](getting-started/langchain.md) needs to restore the value.

The full section catalogue, every component `type`, and the JSON form of the same file are in the [configuration reference](configuration/toml.md).

## Set the secrets in the environment

The hasher pepper and the cipher key are secrets read from the environment at build time, never from the file. A file with a secret in it would leak the secret through version control.

```bash
export PIIGHOST_HASH_PEPPER="a-long-random-string"
export PIIGHOST_CIPHER_KEY="$(openssl rand -base64 32)"
```

`PIIGHOST_HASH_PEPPER` is any non-empty string. `PIIGHOST_CIPHER_KEY` is base64 of 16, 24, or 32 bytes, so `openssl rand -base64 32` gives an AES-256 key. If a [moderation guard](configuration/toml.md) is configured, its `MISTRAL_API_KEY` follows the same rule and lives only in the environment.

!!! warning
    A pepper or key written into the config file cancels the protection. The store leaks alongside the file that decrypts it. Keep both in the process environment or a secrets manager, and rotate them like any production credential. A missing or malformed secret raises `ConfigError` at build time, so the pipeline fails to start rather than running unprotected.

## Load and run

`load_thread_pipeline` reads the file, builds every component, and returns the thread pipeline. It raises `ConfigError` if the file declares no `[memory]`, so a stateless config cannot be loaded here by mistake.

```python
--8<-- "snippets/redis_run.py:example"
```

The `thread_id` scopes the conversation. The same value in a later message of `user-42` keeps its token, and a different `thread_id` never sees it, so two users stay isolated. Behind the scenes the pipeline hashes the message into a Redis key and stores the detections encrypted, so a leak of the Redis disk reveals neither the message nor the confidential data.

## Bound the in-memory store

The default `InMemoryConversationMemory` keeps every thread in a process-local dict, bounded to 10,000 threads and one day idle, so a long-lived process that never calls `forget_thread` does not keep every value it saw. Adjust `max_threads` to cap how many threads are kept, evicting the least recently used beyond it, and `ttl` to expire a thread that many seconds after its last write, dropped lazily on the next access.

```toml title="pipeline.toml"
[memory]
type = "in_memory"
max_threads = 10000
ttl = 3600
```

For a durable or multi-worker deployment, use a persistent backend instead, and forget a thread with `forget_thread` when its conversation ends.

## How the store protects the data

Two protections combine on every write, both keyed by a secret the store never holds.

- The **key is hashed**. The hasher derives a digest of the message under the pepper. `argon2` (Argon2id) is slow and memory-hard, the right choice when the pepper itself might leak. `sha256` (HMAC-SHA256) is fast and fits a busy hot path. Both are deterministic, so the same message always lands on the same key.
- The **value is encrypted**. `aesgcm` (AES-GCM) encrypts the detections before they are written, with a fresh nonce per message. Decryption fails on an altered ciphertext, so tampering is detected.

The `thread_id` stays in the clear as a key namespace, which is what lets a whole thread be enumerated and forgotten with `forget_thread`. The threat model and the backend comparison are in [Security](security.md).

## Use a SQL database instead

If your stack already runs PostgreSQL, `type = "sqlalchemy"` gives the same durable, multi-worker store over any async SQLAlchemy driver. Install `piighost[config,sqlalchemy,crypto,argon2]`, and point the config at an environment variable for the URL so the password stays out of the file.

```toml title="pipeline.toml"
[memory]
type = "sqlalchemy"
url_env = "PIIGHOST_DATABASE_URL"

[memory.hasher]
type = "argon2"

[memory.cipher]
type = "aesgcm"
```

```bash
export PIIGHOST_DATABASE_URL="postgresql+asyncpg://user:pass@db.internal/piighost"
```

The URL must use an async driver (`postgresql+asyncpg://...`, `sqlite+aiosqlite://...`). Create the table once at startup with `await pipeline.memory.create_schema()`. The hasher and cipher protect the stored values exactly as they do for Redis.

## Serve it over HTTP with `piighost-api`

If several applications share the pipeline, or one that is not written in Python needs it, serve the same file with `piighost-api`, the companion server. Its Docker image is `ghcr.io/athroniaeth/piighost-api`. A first server outside Docker is built step by step in [Deploy a de-identification API](getting-started/api-server.md).

```yaml title="compose.yaml"
services:
  piighost-api:
    image: ghcr.io/athroniaeth/piighost-api:latest
    ports:
      - "8000:8000"
    environment:
      - PIIGHOST_CONFIG=/app/pipeline.toml
      - API_KEY_DEFAULT=${API_KEY_DEFAULT}
      - SECRET_PEPPER=${SECRET_PEPPER}
      - PIIGHOST_HASH_PEPPER=${PIIGHOST_HASH_PEPPER}
      - PIIGHOST_CIPHER_KEY=${PIIGHOST_CIPHER_KEY}
      - EXTRA_PACKAGES=piighost[crypto]
    volumes:
      - ./pipeline.toml:/app/pipeline.toml
      - cache:/root/.cache
    depends_on:
      - redis

  redis:
    image: redis:7-alpine

volumes:
  cache:
```

The mounted `pipeline.toml` is the file above, with its `url` set to `redis://redis:6379/0`, the address of the `redis` service. `API_KEY_DEFAULT` holds a key printed by `keyshield generate`, and the server refuses to start without one. The image carries the Redis client and the Argon2 hasher, and `EXTRA_PACKAGES` adds the AES-GCM cipher. The `cache` volume keeps the hub downloads, the model weights and the packages of `EXTRA_PACKAGES` across container restarts.

The image reads these variables:

| Variable | Default | Effect |
|---|---|---|
| `PIIGHOST_CONFIG` | `/app/pipeline.toml` | The config file or hub reference to serve. The image ships a default, every regex group of the hub, which a mounted file or a hub reference replaces |
| `API_HOST` | `0.0.0.0` | Bind host |
| `API_PORT` | `8000` | Bind port |
| `LOG_LEVEL` | `info` | Log level |
| `EXTRA_PACKAGES` | empty | Packages installed with `uv pip install` at container start, such as `piighost[gliner2]` for a configuration that runs GLiNER2 |

To serve a hub configuration instead of a file, set `PIIGHOST_CONFIG` to its reference and add the Redis memory with a `PIIGHOST_MEMORY` variable, as shown in [Server CLI](reference/api-cli.md). Each container runs a single server process, so scale by adding containers on the same Redis memory. Every route, the proxies included, is listed in [API endpoints](reference/api-endpoints.md).

## See also

- [Configuration reference](configuration/toml.md): every section and component `type`, TOML and JSON.
- [Multi-instance deployment](multi-instance.md): why the shared Redis memory is required behind a load balancer.
- [Security](security.md): the at-rest threat model and the backend comparison.
- [Conversational pipeline](getting-started/conversation.md): the thread pipeline API the middleware drives.
- [Store conversations and protect traces](../../openwiki/exploitation/stockage-et-chiffrement.md) (in French): the storage rules, `BR-STO-01` to `BR-STO-08`, written for a DPO or an operator.
