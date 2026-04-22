# Chunked Detector Benchmark — Design

**Date:** 2026-04-22
**Status:** Draft
**Scope:** Measure whether `ChunkedDetector` improves NER quality over a plain NER detector, and find its optimal hyperparameters.

## Motivation

`ChunkedDetector` (`src/piighost/detector/chunked.py`) wraps any `AnyDetector` and splits long texts into overlapping windows before running NER. The hypothesis is that:

1. NER models (GLiNER2, BERT-based) have limited context windows and perform worse on long texts.
2. Overlapping chunks cause the same span to be seen multiple times, which may allow a higher confidence `threshold` to filter noise while still catching every real entity.

We want an empirical answer: **at which `(chunk_size, overlap, threshold)` does chunking beat the plain detector, and by how much?**

## Goals

- Find the optimal `(chunk_size, overlap, threshold)` per detector via grid search.
- Compare chunked vs plain baseline on precision / recall / F1.
- Isolate the effect on long texts (where chunking actually triggers).
- Produce a reproducible benchmark script and a markdown report.

## Non-Goals

- We are not benchmarking spaCy (no confidence threshold).
- We are not optimizing the `ChunkedDetector` implementation itself.
- We are not introducing a new dataset; we reuse `ai4privacy/pii-masking-300k`.
- We are not tuning per-label thresholds (single global threshold per config).

## Decisions

| Axis | Value |
|---|---|
| Detectors | `Gliner2Detector` (`fastino/gliner2-multi-v1`), `TransformersDetector` (`Davlan/xlm-roberta-base-ner-hrl` multilingual) |
| Languages | EN, FR, DE, IT, ES, NL (all 6 dataset languages) |
| `chunk_size` grid | `[128, 256, 384, 512, 768]` |
| `overlap` grid | `[0, 32, 64, 128]` (constraint: `overlap < chunk_size`) → 19 valid `(chunk, overlap)` pairs |
| `threshold` grid | `[0.3, 0.5, 0.7, 0.8, 0.9]` |
| Baseline | Same detector without chunking, swept across the same threshold grid |
| Phase 1 samples | 200 per language (grid search) |
| Phase 2 samples | 1000 per language (final eval on winning config) |
| Long-text strategy | Bucketization on real data + synthetic long texts (concatenation) |
| Optimization metric | Recall @ precision ≥ 0.80, tie-break on F1 |
| Match mode | `partial` (overlap + label match) |

### Total grid size

Chunked configs: 19 (chunk, overlap) × 5 thresholds = 95 per (detector, language).
Baseline configs (no chunking): 5 thresholds per (detector, language).
Grand total phase 1: (95 + 5) × 2 detectors × 6 languages = **1200 configurations** evaluated on 200 samples each.

Optimization: the `threshold` axis can be collapsed by running the detector with `threshold=0.0` once per `(chunk_size, overlap)` (and once for baseline) and filtering detections client-side for each threshold (since the threshold is a post-processing cutoff on confidence). This cuts phase 1 to **(19 + 1) × 2 × 6 = 240 inference runs** × 200 samples. To be verified in implementation: confirm that setting `threshold=0` in `Gliner2Detector` / `TransformersDetector` yields detections whose confidence can be filtered post-hoc without loss.

Phase 2: 1 winning chunked config + 1 baseline × 2 detectors × 6 languages × 1000 samples = manageable.

## Architecture

```
benchmarks/
├── __init__.py
├── __main__.py              # existing CLI (single config eval)
├── dataset.py               # existing loader
├── metrics.py               # existing P/R/F1
├── label_map.py             # existing
├── report.py                # existing formatter
├── runner.py                # existing single-run orchestrator
├── run_all.py               # existing multi-language driver
│
├── chunking/                # NEW — chunking benchmark module
│   ├── __init__.py
│   ├── __main__.py          # CLI: python -m benchmarks.chunking
│   ├── grid.py              # grid-space definition and iteration
│   ├── grid_runner.py       # per-config eval, reuses runner.run_benchmark
│   ├── buckets.py           # length bucketization
│   ├── synthetic.py         # synthetic long-text generator
│   ├── selection.py         # "recall @ precision ≥ 0.80" selection
│   └── report.py            # grid-search-specific table/markdown rendering
│
└── CHUNKING_RESULTS.md      # final markdown report (generated)
```

### Unit responsibilities

- **`grid.py`** — Yields configs `(chunk_size | None, overlap | None, threshold)` with constraint validation. `chunk_size=None` denotes the no-chunking baseline. Pure function, no I/O.
- **`grid_runner.py`** — Iterates the grid, loads each detector model **once** (reused across configs), runs detections at `threshold=0.0`, filters client-side per threshold, calls existing `compute_detection_metrics` for each config. Returns a list of `GridResult(config, per_bucket_metrics, metrics, elapsed)`.
- **`buckets.py`** — Pure function `bucket_of(text_length: int) -> str` returning one of `{"<256", "256-512", "512-1024", ">1024"}`. Aggregates metrics per bucket post-hoc from per-sample detections.
- **`synthetic.py`** — Given a list of short `BenchmarkSample`, concatenates 3–5 of them with a separator (e.g. `"\n\n---\n\n"`) and rewrites annotation offsets to the new positions. Emits `BenchmarkSample` with target length in the `>1024` bucket.
- **`selection.py`** — Given all `GridResult`s, returns the config with maximum recall under `precision ≥ 0.80`, breaks ties on F1. Exposes diagnostic on why certain configs were filtered out.
- **`report.py`** — Renders two artifacts: a per-detector grid heatmap table (markdown) and a final "winner vs baseline" comparison with per-bucket breakdown.

### Data flow (phase 1)

```
ai4privacy dataset
      │ load_samples(lang, limit=200)
      ▼
┌──────────────────────────┐
│ for each detector:       │   ← model loaded once
│   for each (cs, ov):     │   ← chunked run once per pair, threshold=0
│     detections_raw       │
│     for each threshold:  │   ← post-hoc filter
│       filtered           │
│       metrics, bucketize │
│       → GridResult row   │
└──────────────────────────┘
      │
      ▼
selection.pick_winner()
      │
      ▼
CHUNKING_RESULTS.md
```

### Data flow (phase 2)

```
winner config from phase 1
      │
      ▼
load_samples(lang, limit=1000) + synthetic long texts
      │
      ▼
chunked vs baseline @ same threshold, full metrics + per-bucket
      │
      ▼
final report section
```

## CLI

Two new entry points:

```bash
# Full grid search, all detectors, all languages. Produces CHUNKING_RESULTS.md.
python -m benchmarks.chunking grid --output CHUNKING_RESULTS.md

# Single-config sanity run for debugging.
python -m benchmarks.chunking eval \
    --detector gliner2 \
    --chunk-size 384 --overlap 64 --threshold 0.7 \
    --language en --limit 200
```

Flags to support: `--detectors`, `--languages`, `--phase1-limit`, `--phase2-limit`, `--skip-synthetic`, `--resume` (checkpoint).

## Error handling

- **Invalid `(chunk_size, overlap)` pair**: skipped at grid iteration time with a warning, not an error.
- **Detector failure on one sample**: caught, logged, sample counted as "skipped". Error rate reported in the summary.
- **Post-hoc threshold filtering assumption violated**: if detections at `threshold=0.0` do not strictly cover those at `threshold=0.5`, fall back to full threshold-axis inference. Detected by a smoke test at startup (one sample, two threshold settings, diff the detections).
- **Checkpointing**: grid runner writes intermediate JSON every `checkpoint_every` configs (default: every config). On resume, skip configs already present in the checkpoint file.
- **Empty precision denominator**: handled by existing `_safe_metrics` (returns 0).

## Testing

- **Unit tests** for `grid.iterate` (constraint validation, no duplicates), `buckets.bucket_of` (boundaries), `synthetic.concat` (offset correctness — gold annotations still align after concat), `selection.pick_winner` (tie-breaking, precision filter).
- **Integration test** with `ExactMatchDetector` (no model load) running a minimal grid (3 configs, 5 samples) to verify end-to-end shape and report generation.
- **Smoke test** for the post-hoc threshold assumption on real detectors (one sample, Gliner2, threshold 0 vs 0.5, detections at 0.5 are strict subset of ≥0.5-filtered detections at 0).
- No test requires loading the real GLiNER2 / Transformers weights in CI.

## Output

Generated `benchmarks/CHUNKING_RESULTS.md` containing:

1. Run metadata (date, dataset version, samples per phase, grid size).
2. Winner table per detector per language: `(chunk_size, overlap, threshold)` + P/R/F1.
3. Phase 2 comparison: winner chunked vs plain baseline, per length bucket.
4. Synthetic long-text results: winner chunked vs plain baseline on concatenated samples.
5. Top-5 configs per detector (for sensitivity analysis).
6. Time spent per detector.

## Risks & Open Questions

- **Post-hoc threshold validity**: the biggest compute optimization. Must verify per detector. If invalid for Transformers `aggregation_strategy="simple"`, we pay 5× compute on Transformers but not Gliner2.
- **Bucket population imbalance**: if `>1024` bucket is empty in the real-data subset, phase 1 "optimal config" may be biased toward short-text behaviour. Mitigated by phase 2 synthetic long texts being reported separately.
- **Multilingual Transformers model choice**: `Davlan/xlm-roberta-base-ner-hrl` may underperform the per-language DistilBERT used in the existing benchmark. Trade-off: simpler evaluation vs. potentially lower baseline.
- **Branching**: the existing `benchmarks/` suite lives on branch `benchmark` (not merged to master). Implementation plan must decide: merge benchmark branch first, or rebuild on a new branch from master. Default: new branch from `benchmark` → adds `benchmarks/chunking/`.
