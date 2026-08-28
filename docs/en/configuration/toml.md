# Configuration reference

Module: `piighost.config`

A configuration file describes a whole pipeline declaratively. `piighost` reads it as TOML or JSON, chosen by the file suffix, validates it with Pydantic, and builds the pipeline the file describes. This page documents every section and every component `type`.

```python
from piighost.config import load_config, load_pipeline, load_thread_pipeline
```

The `config` extra is required (`pip install piighost[config]`), which pulls in `pydantic-settings`. Unknown keys are rejected, so a typo fails validation rather than being ignored.

---

## Entry points

<div class="wide-table" markdown="1">

| Function | Returns | Builds | Memory |
|----------|---------|--------|--------|
| `load_config(path)` | `PipelineConfig` | nothing, validates only | any |
| `load_pipeline(path)` | `AnonymizationPipeline` | a stateless pipeline | rejects a `[memory]` section |
| `load_thread_pipeline(path)` | `ThreadAnonymizationPipeline` | a thread pipeline | requires a `[memory]` section |

</div>

`load_config` parses and validates a file into a `PipelineConfig` without building any component, so no model loads. `load_pipeline` builds a stateless `AnonymizationPipeline` and raises `ConfigError` if the file declares a `[memory]` section, since a memory describes a thread pipeline. `load_thread_pipeline` builds a `ThreadAnonymizationPipeline` and raises `ConfigError` if the file declares no `[memory]` section.

```python
from piighost.config import load_pipeline, load_thread_pipeline

stateless = load_pipeline("pipeline.toml")       # no [memory]
thread = load_thread_pipeline("thread.toml")     # has [memory]
```

---

## File format

The suffix picks the parser: `.json` is read as JSON, anything else as TOML. The two formats carry the same schema. A section is a TOML table or a JSON object.

```toml
[detector]
type = "regex"
patterns = { EMAIL = '[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}' }

[linker]
type = "exact"

[anonymizer.placeholder]
type = "redact"
```

```json
{
  "detector": { "type": "regex", "patterns": { "EMAIL": "[a-z0-9._%+-]+@[a-z0-9.-]+\\.[a-z]{2,}" } },
  "linker": { "type": "exact" },
  "anonymizer": { "placeholder": { "type": "redact" } }
}
```

---

## Environment overrides

Top-level scalars accept an override from an environment variable prefixed `PIIGHOST_`. The only top-level scalar is `name`, so `PIIGHOST_NAME` overrides the `name` key. Overrides layer above the file, so an environment value wins over the file value.

Secrets are never read from the file. Each is read from its own environment variable at build time, and a missing one raises `ConfigError` from `build()`.

<div class="wide-table" markdown="1">

| Secret | Variable | Format | Used by |
|--------|----------|--------|---------|
| Hash pepper | `PIIGHOST_HASH_PEPPER` | any non-empty string | `[memory.hasher]` |
| Cipher key | `PIIGHOST_CIPHER_KEY` | base64 of 16, 24, or 32 bytes | `[memory.cipher]` |
| Moderation key | `MISTRAL_API_KEY` | Mistral API key | `[guard]` type `moderation` |

</div>

---

## Sections

The top-level keys of a `PipelineConfig`.

<div class="wide-table" markdown="1">

| Section | Required | Meaning |
|---------|----------|---------|
| `name` | no | An optional pipeline name, a top-level scalar overridable by `PIIGHOST_NAME` |
| `[detector]` | yes | The detect stage |
| `[linker]` | yes | The entity linker |
| `[anonymizer]` | yes | The render stage, built on a placeholder factory |
| `[overlap_resolver]` | no | Resolves overlapping detections |
| `[expander]` | no | Re-finds missed occurrences of a detected value |
| `[entity_resolver]` | no | Clusters entities that refer to the same thing |
| `[guard]` | no | Re-checks the output for residual PII |
| `[override]` | no | Forces or vetoes detections via a whitelist and a blacklist |
| `[observation_redactor]` | no | A placeholder factory redacting trace payloads |
| `[memory]` | no | The conversation memory; its presence makes a thread pipeline |

</div>

---

## `[detector]`

Discriminated on `type`. Required.

### `type = "regex"`

Matches PII by one regex per label, pulled from inline `patterns`, named `catalogs`, or both. Catalogs merge first, then inline patterns, so an inline pattern overrides a catalog pattern on the same label. At least one inline pattern or one catalog is required. Each pattern is validated as a compilable regex at load time.

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `patterns` | `dict[str, str]` | `{}` | Inline label-to-regex mapping |
| `catalogs` | `list[str]` | `[]` | Prebuilt catalogs, among `generic`, `us`, `eu`, `fr` |

```toml
[detector]
type = "regex"
catalogs = ["generic", "fr"]
patterns = { EMPLOYEE_ID = 'EMP-[0-9]{4}' }
```

### `type = "composite"`

Runs child detectors together and merges their detections.

| Key | Type | Meaning |
|-----|------|---------|
| `detectors` | `list[detector]` | The child detector configs, at least one, as `[[detector.detectors]]` |

```toml
[detector]
type = "composite"

[[detector.detectors]]
type = "regex"
catalogs = ["generic"]

[[detector.detectors]]
type = "exact"
values = { Patrick = "PERSON" }
```

### `type = "exact"`

Finds occurrences of literal values, each mapped to a label.

| Key | Type | Meaning |
|-----|------|---------|
| `values` | `dict[str, str]` | Literal value to label mapping, at least one |

```toml
[detector]
type = "exact"
values = { Patrick = "PERSON", Lyon = "LOCATION" }
```

### `type = "chunked"`

Wraps a detector with a splitter that cuts long text into overlapping chunks.

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `detector` | `detector` | | The detector run on each chunk, as `[detector.detector]` |
| `chunk_size` | `int` | `1000` | Maximum chunk size, greater than 0 |
| `chunk_overlap` | `int` | `100` | Overlap between chunks, below `chunk_size` |

```toml
[detector]
type = "chunked"
chunk_size = 2000
chunk_overlap = 200

[detector.detector]
type = "spacy"
model = "en_core_web_sm"
```

### Model-backed detectors

Each needs an extra and a model. `labels` accepts a list or an `{emitted: internal}` map. `max_concurrency` caps concurrent inferences, or `None` for unbounded.

<div class="wide-table" markdown="1">

| `type` | Extra | Keys |
|--------|-------|------|
| `gliner2` | `gliner2` | `model` (required), `labels` (required), `threshold` (default `0.5`), `max_concurrency` |
| `spacy` | `spacy` | `model` (required), `labels`, `max_concurrency` |
| `transformers` | `transformers` | `model` (required), `labels`, `threshold` (default `0.0`), `max_concurrency` |
| `llm` | `llm` | `model` (required), `labels` (required), `prompt`, `provider` |

</div>

```toml
[detector]
type = "gliner2"
model = "fastino/gliner2-multi-v1"
labels = ["PERSON", "LOCATION"]
threshold = 0.5
```

The `llm` detector reads its provider credential from the provider's own environment variable, never from the file.

---

## `[linker]`

Discriminated on `type`. Required.

| `type` | Meaning |
|--------|---------|
| `exact` | Groups detections by casefolded value |

```toml
[linker]
type = "exact"
```

---

## `[anonymizer]`

The render stage. Required. It carries one `[anonymizer.placeholder]` table selecting the placeholder factory, discriminated on `type`.

<div class="wide-table" markdown="1">

| `type` | Token | Keys |
|--------|-------|------|
| `redact` | `<<REDACT>>`{ .placeholder } | |
| `label` | `<<PERSON>>`{ .placeholder } | |
| `label_counter` | `<<PERSON:1>>`{ .placeholder } | |
| `label_hash` | `<<PERSON:a1b2c3d4>>`{ .placeholder } | `hash_length` (default `8`) |
| `mask` | `P***`{ .placeholder } | `visible` (default `1`), `mask_char` (default `*`) |

</div>

```toml
[anonymizer.placeholder]
type = "label_counter"
```

The middleware needs a delimited factory, so `redact`, `label`, `label_counter`, or `label_hash`. The `mask` factory produces `P***`{ .placeholder }, which keeps no delimiters and has no recognizer.

---

## `[overlap_resolver]`

Optional. Discriminated on `type`.

| `type` | Meaning |
|--------|---------|
| `confidence` | Keeps the highest-confidence detection when two overlap |

```toml
[overlap_resolver]
type = "confidence"
```

---

## `[expander]`

Optional. Discriminated on `type`.

| `type` | Keys | Meaning |
|--------|------|---------|
| `word_boundary` | `case_sensitive` (default `false`) | Re-finds a detected value's other whole-word occurrences |

```toml
[expander]
type = "word_boundary"
case_sensitive = false
```

---

## `[entity_resolver]`

Optional. Discriminated on `type`.

| `type` | Keys | Meaning |
|--------|------|---------|
| `merge` | | Unions entities that share detections |
| `separate` | | Keeps every entity distinct |
| `fuzzy` | `threshold` (default `0.85`) | Clusters entities at or above a Jaro-Winkler similarity |

```toml
[entity_resolver]
type = "fuzzy"
threshold = 0.85
```

---

## `[guard]`

Optional. Discriminated on `type`. Re-checks the anonymized output for residual PII and refuses it when PII remains.

### `type = "detector"`

Re-runs a detector on the output. Carries a nested `[guard.detector]` config.

```toml
[guard]
type = "detector"

[guard.detector]
type = "regex"
patterns = { EMAIL = '[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}' }
```

### `type = "llm"`

Prompts a chat model to find residual PII.

| Key | Type | Meaning |
|-----|------|---------|
| `model` | `str` | The chat model identifier (required) |
| `labels` | `list` or `dict` | The labels to look for (required) |
| `prompt` | `str` | A prompt overriding the default, or omitted |
| `provider` | `str` | The provider, or omitted to infer from the model |

### `type = "moderation"`

Scores the output with a Mistral moderation model. The credential is read from `MISTRAL_API_KEY` at build time, and `build()` raises `ConfigError` when it is unset.

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `model` | `str` | `mistral-moderation-latest` | The moderation model |
| `threshold` | `float` | `0.5` | The category score at or above which the text is flagged |

---

## `[override]`

Optional. Forces detections through a whitelist and vetoes them through a blacklist. Each list is a detector config, `[override.whitelist]` and `[override.blacklist]`, and both are optional.

<div class="wide-table" markdown="1">

| Key | Values | Default | Meaning |
|-----|--------|---------|---------|
| `[override.whitelist]` | detector | | A detector whose hits are forced into the set |
| `[override.blacklist]` | detector | | A detector whose hits invalidate detections |
| `blacklist_strategy` | `exact`, `value`, `overlap` | `exact` | How a blacklist hit invalidates: same span and label, same casefolded value, or any overlapping span |
| `whitelist_strategy` | `respect_provenance`, `force` | `respect_provenance` | Whether a whitelist hit leaves an assistant-introduced value in clear, or tokenizes it regardless |
| `conflict_strategy` | `whitelist_wins`, `blacklist_wins`, `raise` | `whitelist_wins` | Who wins when the two lists contradict; `raise` refuses the collision with `ConflictingOverrideError` |

</div>

```toml
[override]
blacklist_strategy = "value"

[override.whitelist]
type = "regex"
patterns = { CODENAME = 'ACME-[A-Z]+' }

[override.blacklist]
type = "exact"
values = { "public@corp.com" = "EMAIL" }
```

---

## `[observation_redactor]`

Optional. A placeholder factory config, same `type` values as `[anonymizer.placeholder]`, redacting the payloads sent to a tracing backend so a trace holds tokens, not raw values.

```toml
[observation_redactor]
type = "label"
```

---

## `[memory]`

Optional. Its presence makes the pipeline a `ThreadAnonymizationPipeline` keeping per-thread state. Discriminated on `type`.

### `type = "in_memory"`

A process-local store, lost on restart and not shared across workers.

```toml
[memory]
type = "in_memory"
```

### `type = "redis"`

A persistent, multi-worker store. Each stored value is keyed by a hasher and encrypted by a cipher.

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `url` | `str` | | The Redis connection URL (required) |
| `namespace` | `str` | `piighost` | The key prefix isolating this library's keys |
| `ttl` | `int` | `None` | Seconds a stored message lives, or omitted to keep until eviction |
| `[memory.hasher]` | hasher | | The hasher keying each message (required) |
| `[memory.cipher]` | cipher | | The cipher encrypting each value (required) |

The hasher, `[memory.hasher]`, is discriminated on `type`.

<div class="wide-table" markdown="1">

| `type` | Keys | Meaning |
|--------|------|---------|
| `sha256` | | HMAC-SHA256, a fast keyed digest |
| `argon2` | `time_cost` (default `2`), `memory_cost` (default `19456`), `parallelism` (default `1`), `hash_length` (default `32`) | Argon2id, a slow memory-hard digest |

</div>

The cipher, `[memory.cipher]`, has one type.

| `type` | Meaning |
|--------|---------|
| `aesgcm` | AES-GCM authenticated encryption of stored values |

The hasher reads its pepper from `PIIGHOST_HASH_PEPPER` and the cipher reads its base64 key from `PIIGHOST_CIPHER_KEY`, both at build time. A missing or malformed value raises `ConfigError`.

```toml
[memory]
type = "redis"
url = "redis://localhost:6379/0"
namespace = "piighost"
ttl = 3600

[memory.hasher]
type = "argon2"

[memory.cipher]
type = "aesgcm"
```

### `type = "sqlalchemy"`

A durable, multi-worker store backed by any SQLAlchemy-supported database (SQLite, PostgreSQL, ...). It reads the database URL from an environment variable rather than the config file, so the URL and its password stay out of version control. An optional hasher and cipher protect the stored values exactly as they do for Redis.

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `url_env` | `str` | `PIIGHOST_DATABASE_URL` | The environment variable holding the async database URL |
| `table_name` | `str` | `piighost_conversation_messages` | The table storing per-thread messages |
| `[memory.hasher]` | hasher | | Optional. The hasher keying each message |
| `[memory.cipher]` | cipher | | Optional. The cipher encrypting each value |

The URL must use an async driver, for example `postgresql+asyncpg://...` or `sqlite+aiosqlite://...`. A missing environment variable raises `ConfigError` at build time. Call `await memory.create_schema()` once at startup to create the table.

```toml
[memory]
type = "sqlalchemy"
url_env = "PIIGHOST_DATABASE_URL"
table_name = "piighost_conversation_messages"

[memory.hasher]
type = "argon2"

[memory.cipher]
type = "aesgcm"
```

---

## Full example

A stateless pipeline pulling a catalog, adding one inline pattern, and enabling several optional stages.

```toml
name = "local-en"

[detector]
type = "regex"
catalogs = ["generic"]
patterns = { EMPLOYEE_ID = 'EMP-[0-9]{4}' }

[linker]
type = "exact"

[anonymizer.placeholder]
type = "label_counter"

[overlap_resolver]
type = "confidence"

[expander]
type = "word_boundary"

[entity_resolver]
type = "fuzzy"
threshold = 0.85

[override.whitelist]
type = "regex"
patterns = { CODENAME = 'ACME-[A-Z]+' }

[guard]
type = "detector"

[guard.detector]
type = "regex"
patterns = { EMAIL = '[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}' }

[observation_redactor]
type = "label"
```

The same content in JSON, chosen by a `.json` suffix, is equivalent: a table becomes an object, an inline table becomes a nested object, and an array of tables becomes an array of objects.

---

## Errors

<div class="wide-table" markdown="1">

| Error | Raised when |
|-------|-------------|
| `ConfigFileError` | The file is missing, unreadable, or invalid TOML or JSON |
| `ConfigValidationError` | The parsed data fails schema validation |
| `ConfigError` | A secret is missing at build time, or the wrong entry point is used for the memory declared |

</div>

`ConfigFileError` and `ConfigValidationError` are subclasses of `ConfigError`, so catching `ConfigError` covers all three. The classes live in `piighost.exceptions`, so a caller can catch them without the `config` extra.

---

## See also

- [Command-line interface](../reference/cli.md) for validating a file from the shell.
- [Detectors reference](../reference/detectors.md) for the detector each `type` builds.
- [LangChain middleware reference](../reference/langchain.md) for driving a thread pipeline in an agent.
