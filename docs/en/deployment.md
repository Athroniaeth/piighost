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
from piighost.config import load_thread_pipeline

pipeline = load_thread_pipeline("pipeline.toml")

result = await pipeline.anonymize("Patrick lives in Lyon.", thread_id="user-42")
print(result.text)  # <<PERSON:1>> lives in <<LOCATION:1>>.
```

The `thread_id` scopes the conversation. The same value in a later message of `user-42` keeps its token, and a different `thread_id` never sees it, so two users stay isolated. Behind the scenes the pipeline hashes the message into a Redis key and stores the detections encrypted, so a leak of the Redis disk reveals neither the message nor the PII.

## How the store protects the data

Two protections combine on every write, both keyed by a secret the store never holds.

- The **key is hashed**. The hasher derives a digest of the message under the pepper. `argon2` (Argon2id) is slow and memory-hard, the right choice when the pepper itself might leak. `sha256` (HMAC-SHA256) is fast and fits a busy hot path. Both are deterministic, so the same message always lands on the same key.
- The **value is encrypted**. `aesgcm` (AES-GCM) encrypts the detections before they are written, with a fresh nonce per message. Decryption fails on an altered ciphertext, so tampering is detected.

The `thread_id` stays in the clear as a key namespace, which is what lets a whole thread be enumerated and forgotten with `forget_thread`. The threat model and the backend comparison are in [Security](security.md).

## See also

- [Configuration reference](configuration/toml.md): every section and component `type`, TOML and JSON.
- [Multi-instance deployment](multi-instance.md): why the shared Redis memory is required behind a load balancer.
- [Security](security.md): the at-rest threat model and the backend comparison.
- [Conversational pipeline](getting-started/conversation.md): the thread pipeline API the middleware drives.
