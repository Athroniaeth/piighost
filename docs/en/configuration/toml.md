# TOML pipeline configuration

`piighost` accepts a declarative TOML file that fully describes a
`ThreadAnonymizationPipeline`. The file is consumed by:

- The `piighost-api` server (`piighost-api serve --config <file>`).
- The `piighost validate` and `piighost schema` CLI commands.
- Any application that imports `piighost.config.load_pipeline`.

No Python code runs at load time. The format is fully validated by
Pydantic v2; unknown keys raise an error rather than being silently
ignored.

## Minimal example

```toml
[[detectors]]
type = "regex"
patterns = { EMAIL = "[a-zA-Z0-9._%+\\-]+@[a-zA-Z0-9.\\-]+\\.[a-zA-Z]{2,}" }
```

This produces a pipeline with one regex detector, default span and
entity resolvers, and the `label_counter` placeholder factory
(yielding tokens like `<<EMAIL_1>>`).

## Full example

```toml
[pipeline]
name = "pii-en-multi"
description = "GLiNER2 + regex coverage for English text"
schema_version = 1

[[detectors]]
name = "common"
type = "regex"
patterns = { EMAIL = "[a-z]+@[a-z]+\\.[a-z]+", IP_V4 = "\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b" }

[[detectors]]
name = "gliner2"
type = "gliner2"
model = "fastino/gliner2-multi-v1"
threshold = 0.5
labels = ["person", "city", "email address"]

[span_resolver]
type = "confidence"

[entity_linker]
type = "exact"

[entity_resolver]
type = "merge"

[anonymizer.placeholder_factory]
type = "label_counter"
```

## Reference

### `[pipeline]` (optional)

| Key              | Type    | Default | Meaning                          |
| ---------------- | ------- | ------- | -------------------------------- |
| `name`           | string  | `null`  | Exposed by `/v1/labels`.         |
| `description`    | string  | `null`  | Free-text doc, not used by code. |
| `schema_version` | integer | `1`     | Currently the only valid value.  |

### `[[detectors]]` (required, at least one)

Each entry declares one detector. Multiple entries form an implicit
`CompositeDetector`, in order.

Common keys:

| Key    | Type    | Required | Meaning                                       |
| ------ | ------- | -------- | --------------------------------------------- |
| `type` | string  | yes      | Discriminator (`regex`, `gliner2`, ...).       |
| `name` | string  | no       | Used for `/v1/labels` grouping.               |

Per `type`:

**`regex`**

| Key        | Type             | Required | Meaning                       |
| ---------- | ---------------- | -------- | ----------------------------- |
| `patterns` | table[str, str]  | yes      | Label name to regex pattern.  |

**`gliner2`** (requires `piighost[gliner2]`)

| Key         | Type     | Required | Meaning                              |
| ----------- | -------- | -------- | ------------------------------------ |
| `model`     | string   | yes      | HF model id, e.g. `fastino/gliner2-multi-v1`. |
| `labels`    | list[str]| yes      | Entity types to look for.            |
| `threshold` | float    | no       | Confidence cutoff, default `0.5`.    |
| `flat_ner`  | bool     | no       | Default `true`.                      |

**`spacy`** (requires `piighost[spacy]`)

| Key      | Type     | Required | Meaning                          |
| -------- | -------- | -------- | -------------------------------- |
| `model`  | string   | yes      | spaCy model name.                |
| `labels` | list[str]| yes      | spaCy entity types to keep.      |

**`transformers`** (requires `piighost[transformers]`)

| Key         | Type   | Required | Meaning                              |
| ----------- | ------ | -------- | ------------------------------------ |
| `model`     | string | yes      | HF model id.                         |
| `threshold` | float  | no       | Confidence cutoff, default `0.5`.    |

**`llm`** (requires `piighost[llm]`, secrets in env)

| Key        | Type     | Required | Meaning                              |
| ---------- | -------- | -------- | ------------------------------------ |
| `provider` | string   | yes      | e.g. `openai`, `anthropic`.          |
| `model`    | string   | yes      | Provider-specific model id.          |
| `labels`   | list[str]| yes      | Labels to extract.                   |

API keys are never stored in TOML. They are read from environment
variables by the provider client.

**`chunked`** (wraps another detector)

| Key          | Type           | Required | Meaning                          |
| ------------ | -------------- | -------- | -------------------------------- |
| `chunk_size` | integer (>= 1) | yes      | Character window per chunk.       |
| `overlap`    | integer (>= 0) | no       | Overlap between chunks, default 0. |
| `inner`      | detector cfg   | yes      | The detector to run on each chunk. |

### `[span_resolver]` (optional, default `confidence`)

| `type`        | Behavior                                                            |
| ------------- | ------------------------------------------------------------------- |
| `confidence`  | Keep the highest-confidence detection when spans overlap.            |
| `disabled`    | No conflict resolution.                                              |

### `[entity_linker]` (optional, default `exact`)

| `type`     | Behavior                                                  |
| ---------- | --------------------------------------------------------- |
| `exact`    | Word-boundary regex links repeated mentions.              |
| `disabled` | No cross-mention linking.                                 |

### `[entity_resolver]` (optional, default `merge`)

| `type`     | Behavior                                                  | Extra key |
| ---------- | --------------------------------------------------------- | --------- |
| `merge`    | Union-find merge.                                         |           |
| `fuzzy`    | Jaro-Winkler merge.                                       | `threshold` (float, 0.0..1.0, default `0.85`). |
| `disabled` | No entity merging.                                        |           |

### `[anonymizer]` (optional, default `default`)

```toml
[anonymizer]
type = "default"

[anonymizer.placeholder_factory]
type = "label_counter"     # see below
```

### `[anonymizer.placeholder_factory]` (optional, default `label_counter`)

| `type`            | Token format                       | Extra keys                  |
| ----------------- | ---------------------------------- | --------------------------- |
| `label_counter`   | `<<PERSON_1>>`                     |                             |
| `label_hash`      | `<<PERSON_a1b2c3>>`                | `hash_length` (4..64, default 8) |
| `label`           | `<<PERSON>>` (no disambiguation)   |                             |
| `mask`            | `*****`                            | `mask_char` (1 char, default `*`) |
| `redact_counter`  | `<<REDACTED_1>>`                   |                             |
| `redact_hash`     | `<<REDACTED_a1b2c3>>`              | `hash_length`               |
| `redact`          | `<<REDACTED>>`                     |                             |
| `faker_counter`   | Realistic synthetic value, indexed | `locale` (default `en_US`)  |
| `faker_hash`      | Realistic synthetic value, hashed  | `locale`, `hash_length`     |
| `faker`           | Realistic synthetic value          | `locale`                    |

Faker-based factories require `piighost[faker]`.

## CLI helpers

```
$ piighost validate ./pipeline.toml
OK: pipeline.toml

$ piighost schema > schema.json
```

`schema.json` is the canonical JSON Schema describing the structure
above, suitable for editor autocompletion or any future web UI.
