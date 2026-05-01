# HITL dataset CLI — design spec

## Goal

Build an operational CLI in `piighost-api` that extracts a NER training
dataset from Langfuse traces (HITL corrections + non-HITL anonymize
runs) and computes precision / recall / F1 metrics on it. Replace the
two PEP 723 scripts that currently live in `piighost/examples/observation/`.

## Use cases

1. **HITL-driven dataset**: a human corrects model detections via the
   chat UI; each correction lands in Langfuse as a
   `piighost.hitl_correction` trace. The CLI extracts these into a
   JSONL ground-truth dataset for fine-tuning a NER detector.
2. **Non-HITL "presumed correct" dataset**: when the user accepts the
   model's output without correction, the only Langfuse trace is
   `piighost.anonymize_pipeline`. The CLI extracts these too, marks
   them as model-output (rather than human ground truth), and lets
   downstream tooling decide how to use them (review queue, weak
   supervision, volume bootstrapping).
3. **Continuous evaluation**: the CLI computes per-label P/R/F1 on the
   extracted dataset, optionally split by `source` (hitl vs model) so
   the evaluator can compare model output against human ground truth.

## Non-goals

- Real-time streaming of traces. Extraction is a batch job, run on
  demand or via cron.
- A separate package for the CLI. It ships inside `piighost-api`
  because it consumes the same Langfuse credentials and runs operationally
  next to the inference server.
- Deduplication of records across runs (assumes the user uses
  `--since` / `--until` to scope each batch).
- Cross-thread joins (Langfuse sessions are kept independent in the
  output records; correlation is left to the consumer).

## Architecture

The work spans two repos:

1. **`piighost` (lib)**: change the default of
   `AnonymizationPipeline.observation_ph_factory` from
   `RedactPlaceholderFactory()` to `None`. When `None`, observation
   spans carry the raw user text and raw entity text (no redaction).
   When the caller passes a factory explicitly, the existing redact
   behaviour is preserved and a `PIIGhostConfigWarning` is emitted once
   to flag that the resulting traces will not be extractable for HITL
   dataset / NER evaluation workflows.

2. **`piighost-api` (server)**: a new Typer-based CLI replaces the
   existing argparse `cli.py`. The single binary `piighost-api` now
   ships three subcommands: the existing `serve` plus `dataset extract`
   and `dataset metrics`.

### Lib changes

In `src/piighost/pipeline/base.py`:

- `__init__` parameter `observation_ph_factory` keeps its type
  (`AnyPlaceholderFactory | None`) but its default flips from
  `RedactPlaceholderFactory()` to `None`.
- Internal field `self._obs_ph_factory` is set to the supplied factory
  or `None`. `self._obs_anonymizer` is constructed only when
  `self._obs_ph_factory is not None`.
- A helper `self._obs_text(text, entities)` returns either the raw
  `text` (when `self._obs_anonymizer is None`) or
  `self._obs_anonymizer.anonymize(text, entities)` (when set).
- A helper `self._obs_detection_to_dict(d)` returns
  `_detection_to_dict(d)` (raw) or
  `_detection_to_dict(d, token=self._obs_tokens_for_detections([d])[d])`
  (redacted) depending on factory presence.
- `_obs_tokens_for_detections` keeps its current shape; it is only
  invoked when redaction is active.

`_anonymize_with_span` (in both `pipeline/base.py` and
`pipeline/thread.py`) and `override_detections` (in `thread.py`) are
updated to call the new helpers in place of direct
`_obs_anonymizer.anonymize` / `_obs_tokens_for_detections` calls.

A one-time `PIIGhostConfigWarning` is emitted in `__init__` when
`observation_ph_factory is not None`, with this message:

> observation_ph_factory is set, so observation traces will be redacted
> via this factory. With redaction, the raw user text is no longer
> recoverable from Langfuse, which makes traces unsuitable as input
> for HITL dataset extraction or NER evaluation. Pass
> observation_ph_factory=None (the default) to keep raw text in
> traces, or accept the redaction trade-off if PII must not transit
> the observation backend.

This is a behaviour change on the existing API. Documented in the
piighost CHANGELOG as a `BREAKING CHANGE` for the next minor bump
(0.10.0 → 0.11.0).

### CLI changes (piighost-api)

`piighost-api/pyproject.toml`:

- Add to `dependencies`: `typer>=0.12`.
- Add to `[project.optional-dependencies]`:
  `dataset = ["langfuse>=3.0"]`.
- Keep the existing `[project.scripts] piighost-api =
  "piighost_api.cli:main"`.

`piighost-api/src/piighost_api/cli.py` is rewritten using Typer:

```python
import typer

app = typer.Typer(no_args_is_help=True, add_completion=False)
dataset_app = typer.Typer(no_args_is_help=True, help="HITL dataset operations.")
app.add_typer(dataset_app, name="dataset")

@app.command()
def serve(
    pipeline: str = typer.Argument(..., help="Pipeline import path module:variable."),
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8000),
    log_level: str = typer.Option("info"),
) -> None: ...

@dataset_app.command("extract")
def dataset_extract(
    output: Path = typer.Option(..., "--output", "-o"),
    since: Optional[datetime] = typer.Option(None, "--since"),
    until: Optional[datetime] = typer.Option(None, "--until"),
    mode: DatasetMode = typer.Option(DatasetMode.all, "--mode"),
    limit: Optional[int] = typer.Option(None, "--limit"),
) -> None: ...

@dataset_app.command("metrics")
def dataset_metrics(
    input: Path = typer.Option(..., "--input", "-i"),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
    output_format: OutputFormat = typer.Option(OutputFormat.table, "--output-format"),
    match_mode: MatchMode = typer.Option(MatchMode.strict, "--match-mode"),
    iou_threshold: float = typer.Option(0.5, "--iou-threshold"),
    source_filter: SourceFilter = typer.Option(SourceFilter.all, "--source"),
) -> None: ...

def main() -> None:
    app()
```

`DatasetMode`, `OutputFormat`, `MatchMode`, `SourceFilter` are `enum.Enum`
subclasses scoped to the CLI module. The actual extraction and metrics
logic lives in two new modules:

- `piighost_api/dataset/extract.py`: pure functions to query Langfuse,
  shape records, write JSONL.
- `piighost_api/dataset/metrics.py`: pure functions to aggregate per-label
  TP/FP/FN, render tables / CSV / JSON. Reuses the algorithms already
  proven in `examples/observation/compute_hitl_metrics.py`.

The CLI module is a thin Typer adapter; logic stays testable as plain
Python.

### Extraction logic

Three modes determine which Langfuse traces are pulled.

| Mode         | Pulls                                | Uses for `entities`         |
|--------------|---------------------------------------|-----------------------------|
| `hitl`       | name == `piighost.hitl_correction`   | HITL `output.detections`    |
| `model-only` | name == `piighost.anonymize_pipeline`| `piighost.detect` child output |
| `all`        | both                                  | per-trace                   |

For each trace, the writer emits one JSONL record:

```jsonl
{
  "text": "Bonjour Patrick, comment vas tu ?",
  "entities": [[8, 15, "ORG"]],
  "model_entities": [],
  "labels_universe": ["PERSON","LOCATION"],
  "source": "hitl",
  "trace_id": "...",
  "session_id": "...",
  "created_at": "..."
}
```

- `source`: `"hitl"` for `piighost.hitl_correction` traces, `"model"`
  for `piighost.anonymize_pipeline` traces.
- For `source="hitl"`: `entities` = human-corrected detections,
  `model_entities` = the `before` snapshot from
  `input.detections`.
- For `source="model"`: `entities` = the model output (presumed
  correct), `model_entities` = the same list (kept for symmetry, so
  consumers can write uniform code).
- `labels_universe`: from `input.labels` if present, else `[]`.
- A trace whose `input.text` is missing (e.g. an old trace from before
  the lib change) is skipped silently. The CLI logs the count at the
  end.

### Metrics logic

Reuses the algorithms from
`examples/observation/compute_hitl_metrics.py` (strict / lenient
matching, per-label TP/FP/FN, macro / micro averages, label confusion
matrix). New flag `--source {all,hitl,model}` filters the records
before aggregation:

- `--source hitl`: metrics on human-validated ground truth only
  (strongest signal, low volume).
- `--source model`: metrics on presumed-correct records only (high
  volume, weaker signal — interesting only when paired with offline
  re-validation).
- `--source all` (default): everything.

Output formats: `table` (aligned text), `csv`, `json`.

### JSONL schema (canonical)

```json
{
  "text": "string, raw user input",
  "entities": [[int, int, "string"], "..."],
  "model_entities": [[int, int, "string"], "..."],
  "labels_universe": ["string", "..."],
  "source": "hitl | model",
  "trace_id": "string",
  "session_id": "string | null",
  "created_at": "ISO 8601 string"
}
```

### Migration

The migration spans two repos that release independently.

- In **piighost-api**: the new CLI ships in 0.7.0. The
  `[project.optional-dependencies] dataset` extra brings in
  `langfuse>=3.0`. Users install with
  `pip install piighost-api[dataset]` and run `piighost-api dataset extract`.
- In **piighost**: 0.11.0 ships the `observation_ph_factory` default
  flip and removes the two PEP 723 scripts in
  `examples/observation/`. The CHANGELOG documents the breaking
  default change and the script removal, with a one-line pointer to
  the new piighost-api CLI for the equivalent functionality.
- Order of release: piighost 0.11.0 first (so the CLI consumes traces
  with raw text), then piighost-api 0.7.0 with the CLI. piighost-api
  pins `piighost>=0.11`. A user who pulls a stale piighost (0.10.x)
  with the new CLI gets `model-only` traces with redacted
  `input.text`, which the CLI skips and reports in its summary; no
  hard crash.

## Edge cases

- **No traces match the time window**: write an empty JSONL, log
  "wrote 0 records".
- **Trace lacks `input.text`** (older trace before the lib change):
  skipped, counted in the final summary.
- **Trace lacks a `piighost.detect` child** in `model-only` mode:
  skipped, counted in the final summary.
- **Pipeline configured with explicit `observation_ph_factory`**: the
  warning fires at startup; subsequent traces carry redacted text and
  the CLI's mode `model-only` skips them with a count. `hitl` mode
  still works because HITL traces carry raw text regardless of the
  observation factory (the HITL trace was rewired in the previous
  feature work to always include `input.text`).
- **Langfuse credentials missing**: CLI exits non-zero with a clear
  message that points at the env vars to set
  (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`).

## Testing

### Lib (`piighost`)

- `test_anon_result_cache.py` adds a regression test that
  `AnonymizationPipeline(detector=...)` (no `observation_ph_factory`
  arg) does not redact `input.text` in the recorded span.
- A second test that
  `AnonymizationPipeline(observation_ph_factory=RedactPlaceholderFactory())`
  emits a `PIIGhostConfigWarning` once and continues to redact as
  before.
- The existing HITL tests are revisited so their assertions reflect
  raw text instead of redacted text in detection objects.

### CLI (`piighost-api`)

- `tests/test_dataset_extract.py` (new): unit-tests the record shaping
  with a fake Langfuse client (a `MagicMock` returning hand-crafted
  trace dicts). Covers each mode and the `input.text` skip path.
- `tests/test_dataset_metrics.py` (new): unit-tests the aggregation
  function for strict and lenient matching, with the `--source` filter
  applied. Reuses fixtures from the deleted PEP 723 script's tests if
  they exist.
- `tests/test_cli.py`: smoke test the Typer app via `CliRunner` for
  `--help`, `serve --help`, `dataset extract --help`,
  `dataset metrics --help`.

## Out of scope

- A length-preserving redaction strategy (`*` masking, type-letter
  masking, etc.) for the observation factory. Easy follow-up: ship a
  `StarMaskPlaceholderFactory` next to the existing factories. No lib
  change needed once shipped.
- A `RedactStrategy` enum on the pipeline. The current
  factory-injection contract is enough.
- Real-time streaming export. Out of scope for this batch CLI.
- A web UI for browsing the JSONL. Out of scope; consumers can use
  any standard JSONL viewer.
