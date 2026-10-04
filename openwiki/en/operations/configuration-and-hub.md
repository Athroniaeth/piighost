---
type: operations
title: Configure a pipeline by file, hub and command line
description: How to describe a PIIGhost pipeline in a TOML or JSON file, override it from the environment, pull pattern catalogs from the hub, supply the secrets and check it all with the piighost command.
tags: [configuration, toml, hub, cli, secrets, environment]
verified:
  - by: openwiki/0.6.1
    at: 2026-10-01T18:36:49.731Z
sources:
  - id: openwiki-source-edd617907d8703b014c2a6c7
    resource: repo://src/piighost/cli/__init__.py
  - id: openwiki-source-845a3e90c784289b153f646a
    resource: repo://src/piighost/config/models/cipher.py
  - id: openwiki-source-41e1e26a4994aaf47da714b8
    resource: repo://src/piighost/config/models/detector.py
  - id: openwiki-source-7ef27c7836ed8bc6a9f4f484
    resource: repo://src/piighost/config/models/hasher.py
  - id: openwiki-source-884a2e563fa6c83993666a78
    resource: repo://src/piighost/config/models/memory.py
  - id: openwiki-source-78a981471914dd9a421617be
    resource: repo://src/piighost/config/settings.py
  - id: openwiki-source-025fa1ad7c6dbf188e59fca7
    resource: repo://src/piighost/hub.py
generated: { by: "claude-code", at: "2026-10-01T18:36:49.731Z" }
---

# Configure a pipeline by file, hub and command line

## In short

- A text file (TOML or JSON) describes the whole protection chain, that is what to look for, how to replace it, where to keep the conversation memory.
- The file never contains a secret. Keys and passwords come from the server's environment variables.
- Pattern lists (e-mails, card numbers, etc.) can come from an online registry, the hub. A pinned version is downloaded once, then read locally.
- The `piighost validate` command checks a file without starting anything. It fits an automatic check before going to production.
- A typo in the file is rejected, never ignored.

There is no graphical interface. All configuration goes through this file and the command line. The terms are defined in the [glossary](../glossary.md). Each section and each key of the file is listed in the [configuration reference](../../../docs/en/configuration/toml.md) of the technical guide. The [configuration tutorial](../../../docs/en/getting-started/configuration.md) builds a file step by step.

## Choose how to load the configuration

| You want to… | Call | Result |
|---|---|---|
| Check a file without building anything | `load_config(source)` or `piighost validate` | a validated `PipelineConfig`, no model loaded |
| Protect standalone texts | `load_pipeline(source)` | an `AnonymizationPipeline` |
| Protect a conversation | `load_thread_pipeline(source)` | a `ThreadAnonymizationPipeline` |

`source` is a file path or a hub reference (`hub:piighost/generic`). The `.json` suffix selects the JSON reader, any other suffix the TOML reader (`config/settings.py:54-69`).

## Write a minimal file

The smallest valid file declares only a detector (`examples/config/detector_only.toml`):

```toml
[detector]
type = "regex"
patterns = { EMAIL = '[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}' }
```

The entity linker, the anonymizer and the overlap resolver take their default value. An address becomes `<<EMAIL:1>>`. Other examples are in `examples/config/`, namely `pipeline.toml`, `thread_redis.toml`, `thread_sqlalchemy.toml`, `minimal.json`.

## Rules to know

**BR-CFG-01.** When the file contains an undeclared key, then loading fails with `ConfigValidationError`. For example, `[detectr]` instead of `[detector]` is rejected.

**BR-CFG-02.** When the file declares a `[memory]` section, then it describes a conversation pipeline. `load_pipeline` rejects it with `this configuration declares a memory; use load_thread_pipeline`. Conversely, `load_thread_pipeline` rejects a file without `[memory]`.

**BR-CFG-03.** When `token_memo_ttl` is set without a `[memory]` section, then validation fails. Only a conversation pipeline keeps this cache.

**BR-CFG-04.** When a value is given in several places, then explicit arguments take precedence, then the `PIIGHOST_*` variables, then the file or hub.

**BR-CFG-05.** When a variable targets a subkey, such as `PIIGHOST_DETECTOR__TYPE`, then it has no effect, because no nested delimiter (the `__` that separates a section from its key) is configured. You override a whole section with a JSON object, for example `PIIGHOST_DETECTOR='{"type": "exact", "values": {"Patrick": "PERSON"}}'`.

**BR-CFG-06.** When a secret is missing, then the `ConfigError` error occurs at build time, not at validation. `piighost validate` therefore accepts a file whose secrets are not supplied yet.

**BR-CFG-07.** When a hub reference ends with eight hexadecimal characters (a commit), then the response is cached on disk and never downloaded again. A reference that ends with a tag, or has no selector (`latest`), is downloaded again at each build.

**BR-CFG-08.** When a regex detector combines catalogs and inline patterns, then the catalogs merge in order, then the inline patterns. On the same label, the last one wins, so an inline pattern overrides any catalog.

**BR-CFG-09.** When a catalog is named `generic`, `us`, `eu` or `fr` without a hub prefix, then it is rejected with the hub reference that replaces it (`hub:piighost/generic`).

## Supply the secrets

Secrets are read from the environment only. Never write them in the file.

| Secret | Variable | Used by | Error if missing |
|---|---|---|---|
| Hashing pepper | `PIIGHOST_HASH_PEPPER` | `[memory.hasher]` | `a hasher requires the PIIGHOST_HASH_PEPPER environment variable to be set` |
| Encryption key (base64) | `PIIGHOST_CIPHER_KEY` | `[memory.cipher]` | `the cipher requires the PIIGHOST_CIPHER_KEY environment variable to be set` |
| Database URL | value of `url_env`, `PIIGHOST_DATABASE_URL` by default | `[memory]` of type `sqlalchemy` | `The SQLAlchemy memory needs the … environment variable holding the database URL` |
| Mistral key | `MISTRAL_API_KEY` | `moderation` guard rail | `ConfigError` at build time |

The non-secret variables read elsewhere are `PIIGHOST_HUB_URL` (private registry), `XDG_CACHE_HOME` (root of the hub cache), `PIIGHOST_API_URL` and `PIIGHOST_HOOK_LOG` (Claude Code hooks, see [Plug the protection into an agent](../integrations/agents-and-tools.md)).

## Pull patterns from the hub

The hub is the only source of patterns. The library ships none. A reference is written `namespace/name`, with an optional `:tag` or `:commit` selector, and the optional `hub:` prefix.

- Origin: `https://hub.piighost.dev`, or `PIIGHOST_HUB_URL`. Only `http` and `https` are accepted.
- Timeout: 10 seconds (`hub.py:44`).
- Cache: `$XDG_CACHE_HOME/piighost/hub/`, otherwise `~/.cache/piighost/hub/`. The file name is a SHA-256 digest of the URL.
- A regex detector takes only the `?part=detector` part. If the reference describes a model detector, loading raises `HubPayloadError`. In that case, load the whole configuration with `load_config("hub:…")`.

## Check from the command line

The `piighost` command needs the `config` extra (typer). Without it, it prints `The piighost CLI requires typer. Install it with: pip install piighost[config]` and exits with code 1.

| Command | Effect | Exit code |
|---|---|---|
| `piighost validate <file or hub:…>` | Validates without building. Prints `OK: <path>`. | 0 if valid, 1 on `ConfigError` or `HubError` |
| `piighost schema` | Prints the JSON schema of `PipelineConfig`. | 0 |
| `piighost anonymize "<text>"` | Builds and runs the pipeline. Reads standard input with `-` or with no argument. | 0, or 1 on a config or hub error |

The options of `anonymize` are `--config <file>`, `--api <url>` (mutually exclusive, otherwise `Pass at most one of --config and --api.`), `--thread-id` (default `default`), `--json`. Without `--config` or `--api`, the command runs a regex detector on `hub:piighost/generic:fab51b33` (e-mail, URL, IPv4, card number).

### Check

```bash
uv run piighost validate examples/config/pipeline.toml
echo "Write to claire.dubois@example.com" | uv run piighost anonymize --config examples/config/detector_only.toml
```

The first command prints `OK: examples/config/pipeline.toml`. The second prints `Write to <<EMAIL:1>>`.

## Pitfalls

- **`validate` does not prove that the pipeline starts.** Secrets, hub catalogs and models are read only at build time (BR-CFG-06).
- **Building a file that names a catalog calls the network** on the first run. A server without outbound access fails with `HubUnreachableError`, unless the cache is already filled.
- **A non-writable cache is silently ignored** (`hub.py:268-278`). The pipeline then downloads again at each start.
- **`anonymize` catches only `ConfigError` and `HubError`.** A missing extra or a guard rail that blocks (`PIIRemainingError`) surfaces as a full Python traceback.
- **`--thread-id` is `default` by default.** Two calls without an identifier share the same conversation on a conversation pipeline.

## Where the rules live

| Rule | Location |
|---|---|
| BR-CFG-01 | `config/settings.py:97` (`extra="forbid"` of `PipelineConfig`), `config/models/common.py:13` (the same rejection in each section) |
| BR-CFG-02 | `config/settings.py:236-262` (`load_pipeline` and `load_thread_pipeline`) |
| BR-CFG-03 | `config/settings.py:114-127` (`_token_memo_ttl_needs_a_memory`) |
| BR-CFG-04 | `config/settings.py:129-143` (`settings_customise_sources`) |
| BR-CFG-05 | `config/settings.py:97` (`env_prefix="PIIGHOST_"`, without a nested delimiter) |
| BR-CFG-06 | `config/models/hasher.py:40` and `config/models/cipher.py:26-40` (`build`, which reads the secret) |
| BR-CFG-07 | `hub.py:144-162` (`_read`, the cache of commit references only) |
| BR-CFG-08 | `config/models/detector.py:101-115` (`build`, catalogs then inline patterns) |
| BR-CFG-09 | `config/models/detector.py:53-74` (`_catalogs_are_hub_refs`) |

## Tests

| Test | Covers |
|---|---|
| `tests/config/test_settings.py` | File errors, order of precedence on a scalar (`PIIGHOST_NAME`), build of each stage |
| `tests/cli/test_cli.py` | Exit codes of `validate`, `schema`, `anonymize`, mutual exclusion of `--config`/`--api` |
| `tests/test_hub.py` | Reference parsing, private origin, rejection of a model detector, pinned cache, moving selector never cached |
| `tests/config/test_hub_config.py` | Loading a whole configuration from the hub |

Overriding a whole section with a JSON object is not covered in `test_settings.py`. [to check]: add a test that sets `PIIGHOST_DETECTOR` to confirm BR-CFG-05.

See also [Store conversations and protect traces](storage-and-encryption.md) for the `[memory]` section.
