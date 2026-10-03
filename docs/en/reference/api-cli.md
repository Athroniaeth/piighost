---
icon: lucide/terminal
---

# Server CLI reference

Package: `piighost-api`

`piighost-api` is the command line of the companion server. `serve` starts the HTTP server. The `dataset` commands build and score a detection dataset from observation traces.

```text
piighost-api serve [--config SOURCE] [--host HOST] [--port PORT] [--log-level LEVEL]
piighost-api dataset extract --output FILE [--since DATE] [--until DATE] [--mode MODE] [--limit N]
piighost-api dataset metrics --input FILE [--output FILE] [--output-format FORMAT] [--match-mode MODE] [--iou-threshold FLOAT] [--source SOURCE]
```

The server requires Python 3.12 or later and `piighost>=2.0,<3`. Its extras add optional features:

| Extra | Adds |
|---|---|
| `gliner2` | `piighost[gliner2]`, for a configuration that runs a GLiNER2 detector |
| `observation` | the OpenTelemetry SDK and OTLP exporter, for exporting traces |
| `dataset` | the Langfuse SDK and `python-dotenv`, for `dataset extract` |

```bash
pip install "piighost-api[gliner2,observation]"
```

---

## `piighost-api serve`

Builds the pipeline once and serves the [API endpoints](api-endpoints.md) with uvicorn, in a single process.

```bash
piighost-api serve --config hub:piighost/support-en:286909f6 --host 0.0.0.0 --port 8000
```

| Option | Default | Description |
|---|---|---|
| `--config`, `-c` | `PIIGHOST_CONFIG` | A TOML or JSON pipeline config file, or a hub reference such as `hub:piighost/support-en:286909f6` |
| `--host` | `127.0.0.1` | Bind host |
| `--port` | `8000` | Bind port |
| `--log-level` | `info` | `debug`, `info`, `warning` or `error` |

- With neither `--config` nor `PIIGHOST_CONFIG`, the command prints `Missing --config or PIIGHOST_CONFIG.` with a usage hint and exits `1`. A file path that does not exist exits `1` with `Configuration file not found:`.
- A hub reference loads the whole configuration the [piighost hub](https://hub.piighost.dev) publishes under that name. A reference pinned to a commit is fetched on the first start and read from the disk cache afterwards.
- A configuration that declares no `[memory]` section is served with the in-process memory, `in_memory`. Its threads live in the server process, so every instance holds its own. Several instances behind a load balancer need a shared `redis` or `sqlalchemy` memory, see [Multi-instance deployment](../multi-instance.md).
- Any top-level section can be overridden with a `PIIGHOST_` variable holding a JSON object, as for a file, see [Environment overrides](../configuration/toml.md). `PIIGHOST_MEMORY` thus adds a shared memory to a hub configuration. The memory in the example below needs `piighost[crypto]` for its cipher.
- Without a key in an `API_KEY_` variable, the server refuses to start unless `PIIGHOST_ALLOW_ANONYMOUS` is set.

```bash
export PIIGHOST_MEMORY='{"type": "redis", "url": "redis://redis:6379/0", "hasher": {"type": "argon2"}, "cipher": {"type": "aesgcm"}}'
piighost-api serve --config hub:piighost/support-en:286909f6
```

---

## Environment variables

<div class="wide-table" markdown="1">

| Variable | Default | Effect |
|---|---|---|
| `PIIGHOST_CONFIG` | none | Config file or hub reference, read when `--config` is absent |
| `API_KEY_<NAME>` | none | One accepted API key per variable. The value is one printed by `keyshield generate` |
| `SECRET_PEPPER` | `keyshield`'s built-in pepper, with a warning | Pepper of the Argon2 hash the server keeps of each key, printed by `keyshield pepper` |
| `PIIGHOST_ALLOW_ANONYMOUS` | off | `1`, `true`, `yes` or `on` lets the server start with no key, every route then open. Also applies when the keys fail to load |
| `PIIGHOST_MAX_BODY_BYTES` | `1000000` | Largest request body accepted, beyond it `413` |
| `PIIGHOST_RATE_LIMIT` | off | `<unit>:<count>` per client, `unit` one of `second`, `minute`, `hour`, `day`, such as `minute:300`. A malformed value stops the server at start |
| `PIIGHOST_OPENAI_UPSTREAM` | `https://api.openai.com/v1` | Upstream of `/openai/v1` when a request names none |
| `PIIGHOST_ANTHROPIC_UPSTREAM` | `https://api.anthropic.com/v1` | Upstream of `/anthropic/v1` when a request names none |
| `PIIGHOST_ANTHROPIC_ANONYMIZE_SYSTEM` | `false` | `1`, `true`, `yes` or `on` de-identifies the system prompt too |
| `PIIGHOST_ANTHROPIC_PLACEHOLDER_NOTE` | empty, no note | `default` adds the built-in note on placeholders. Any other text is used as the note itself |
| `PIIGHOST_ANTHROPIC_NOTE_PLACEMENT` | `system` | `user` puts the note in the first user message, any other value in the system prompt |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`, `OTEL_EXPORTER_OTLP_ENDPOINT` | none | An OTLP endpoint turns on trace export. When both are set, the first one listed wins. Needs the `observation` extra |
| `OTEL_SERVICE_NAME` | `piighost-api` | Service name of the exported traces |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | none | Credentials of `dataset extract` |

</div>

The pipeline reads its own secrets: `PIIGHOST_HASH_PEPPER`, `PIIGHOST_CIPHER_KEY`, `PIIGHOST_DATABASE_URL` and `MISTRAL_API_KEY`. `PIIGHOST_HUB_URL` names a private hub. These variables are listed in the [TOML reference](../configuration/toml.md). The other `OTEL_*` variables, headers included, are read by the OpenTelemetry exporter itself, see [Observation](../observation.md).

The Docker image reads four more, listed in [Deploy a production pipeline](../deployment.md).

---

## `piighost-api dataset extract`

Reads traces from Langfuse and writes one JSONL record per trace. It needs the `dataset` extra and `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`, read from the environment or from a `.env` file in the working directory. Without them, it exits `1`.

```bash
piighost-api dataset extract --output dataset.jsonl --since 2026-09-01 --limit 1000
```

| Option | Default | Description |
|---|---|---|
| `--output`, `-o` | required | JSONL file to write |
| `--since` | none | Skip traces older than this date, `%Y-%m-%d`, `%Y-%m-%dT%H:%M:%S` or `%Y-%m-%d %H:%M:%S` |
| `--until` | none | Skip traces newer than this date, same formats |
| `--mode` | `all` | `hitl`, `model-only` or `all` |
| `--limit` | none | Stop after this many records |

| `--mode` | Trace name read | `entities` taken from |
|---|---|---|
| `hitl` | `piighost.hitl_correction` | the trace output's `detections`, the human correction |
| `model-only` | `piighost.anonymize` | the output `detections` of its `piighost.detect` child |
| `all` | both | per trace |

!!! warning
    No route of the server emits `piighost.hitl_correction`, so `hitl` finds no trace. A corrected message is traced as `piighost.anonymize`, like any other, and `model-only` reads it as a model trace.

A trace without input text, or a model trace without its `piighost.detect` child, is skipped. The command ends with `Wrote N records to FILE (M skipped).`

```json
{
  "text": "Hi Jane Doe, from Acme in Boston",
  "entities": [[3, 11, "PERSON"], [18, 22, "ORGANIZATION"], [26, 32, "LOCATION"]],
  "model_entities": [[3, 11, "PERSON"], [18, 22, "LOCATION"]],
  "labels_universe": [],
  "source": "hitl",
  "trace_id": "...",
  "session_id": "...",
  "created_at": "..."
}
```

| Field | Content |
|---|---|
| `entities` | The reference spans as `[start, end, label]`. They are the human correction for a `hitl` record, and the model output for a `model` record |
| `model_entities` | The model's spans, equal to `entities` on a `model` record |
| `labels_universe` | The `labels` of a correction trace's input, empty on a `model` record |
| `source` | `hitl` or `model` |

---

## `piighost-api dataset metrics`

Scores the model against the reference of a JSONL file written by `dataset extract`, label by label. It needs no extra.

```bash
piighost-api dataset metrics --input dataset.jsonl
```

| Option | Default | Description |
|---|---|---|
| `--input`, `-i` | required | JSONL file to read |
| `--output`, `-o` | stdout | File to write the report to |
| `--output-format` | `table` | `table`, `csv` or `json` |
| `--match-mode` | `strict` | `strict` matches span and label exactly, `lenient` matches a same-label span whose overlap ratio reaches `--iou-threshold` |
| `--iou-threshold` | `0.5` | Overlap floor in `lenient` mode |
| `--source` | `all` | `hitl`, `model` or `all`, the records to score |

On the record above, the table reads:

```text
label                    tp     fp     fn      P      R     F1
--------------------------------------------------------------
LOCATION                  0      1      1   0.00   0.00   0.00
ORGANIZATION              0      0      1   0.00   0.00   0.00
PERSON                    1      0      0   1.00   1.00   1.00
--------------------------------------------------------------
macro avg                 -      -      -   0.33   0.33   0.33
micro avg                 -      -      -   0.50   0.33   0.40

Label confusion (model -> human, same span):
  LOCATION -> ORGANIZATION: 1
```

`tp` counts a model span the reference holds, `fp` a model span it lacks, `fn` a reference span the model missed. `P`, `R` and `F1` are the precision, the recall and their harmonic mean. The confusion section lists the spans where model and reference agree on the offsets and differ on the label.

---

## See also

- [API endpoints](api-endpoints.md): every route the server serves.
- [Deploy a de-identification API](../getting-started/api-server.md): a first server, step by step.
- [CLI](cli.md): the `piighost` command of the library.
