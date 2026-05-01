# HITL Dataset CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flip piighost's observation default to raw text and add a Typer-based `piighost-api dataset extract|metrics` CLI that builds a NER training JSONL from Langfuse traces (HITL corrections + non-HITL anonymize runs).

**Architecture:** The work spans two repos. Phase 1 modifies the piighost library at `~/PycharmProjects/piighost`: `AnonymizationPipeline.observation_ph_factory` defaults to `None` (raw text in observation traces) instead of `RedactPlaceholderFactory()`. New helpers `_obs_text` and `_obs_detection_to_dict` centralise the redact-or-not branching. Phase 2 moves to `~/PycharmProjects/piighost-api` and replaces the existing argparse CLI with a Typer one that adds a `dataset` subcommand group; the two example PEP 723 scripts in `piighost/examples/observation/` are removed.

**Tech Stack:** Python 3.12, pytest-asyncio, ruff, pyrefly, typer, langfuse v3 SDK, msgspec.

**Spec:** `docs/superpowers/specs/2026-05-01-hitl-dataset-cli-design.md`

**No version bumps.** All commits land on master without a release.

---

## File Structure

### piighost (lib) — `~/PycharmProjects/piighost`

| File | Role | Action |
|---|---|---|
| `src/piighost/pipeline/base.py` | `AnonymizationPipeline` base class with obs helpers | Modify (default flip, helpers, warning) |
| `src/piighost/pipeline/thread.py` | `ThreadAnonymizationPipeline` extending base | Modify (use helpers in `_anonymize_with_span` and `override_detections`) |
| `tests/pipeline/test_anon_result_cache.py` | Tests for cache + HITL trace | Modify (assertions reflect raw default; new tests for warning) |
| `examples/observation/export_hitl_dataset.py` | PEP 723 exporter | Delete |
| `examples/observation/compute_hitl_metrics.py` | PEP 723 metrics | Delete |

### piighost-api (server) — `~/PycharmProjects/piighost-api`

| File | Role | Action |
|---|---|---|
| `pyproject.toml` | Project metadata + deps | Modify (add typer, dataset extra) |
| `src/piighost_api/cli.py` | argparse CLI | Replace (Typer-based, multi-subcommand) |
| `src/piighost_api/dataset/__init__.py` | Package init | Create |
| `src/piighost_api/dataset/extract.py` | Langfuse → JSONL pure functions | Create |
| `src/piighost_api/dataset/metrics.py` | JSONL → P/R/F1 pure functions | Create |
| `tests/test_cli.py` | CLI tests | Replace (Typer `CliRunner` based) |
| `tests/test_dataset_extract.py` | Extraction tests | Create |
| `tests/test_dataset_metrics.py` | Metrics tests | Create |

The `dataset` package is split into pure-function modules (no Typer
dependency in business code) so the CLI module stays a thin adapter.

---

## Phase 1 — piighost lib

### Task 1: Add obs helpers and flip the default

Make `observation_ph_factory` optional with `None` as default, expose
two helpers (`_obs_text`, `_obs_detection_to_dict`) that branch on
factory presence, and emit a `PIIGhostConfigWarning` when the caller
sets a factory explicitly.

**Files:**
- Modify: `src/piighost/pipeline/base.py`
- Modify: `tests/pipeline/test_anon_result_cache.py`

- [ ] **Step 1: Write the warning-emission test**

In `tests/pipeline/test_anon_result_cache.py`, add this test inside
`TestAnonResultCacheThread`:

```python
async def test_explicit_obs_factory_emits_config_warning(self) -> None:
    import warnings

    from piighost.exceptions import PIIGhostConfigWarning
    from piighost.placeholder import RedactPlaceholderFactory

    cache = SimpleMemoryCache()
    detector = ExactMatchDetector([("Patrick", "PERSON")])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", PIIGhostConfigWarning)
        ThreadAnonymizationPipeline(
            detector=detector,
            anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
            cache=cache,
            observation_ph_factory=RedactPlaceholderFactory(),
        )
    relevant = [w for w in caught if issubclass(w.category, PIIGhostConfigWarning)]
    assert len(relevant) == 1
    assert "observation_ph_factory" in str(relevant[0].message)
    assert "redacted" in str(relevant[0].message).lower()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/pipeline/test_anon_result_cache.py::TestAnonResultCacheThread::test_explicit_obs_factory_emits_config_warning -v`

Expected: FAIL — no warning is emitted today; `len(relevant) == 0`.

- [ ] **Step 3: Modify `AnonymizationPipeline.__init__` to flip default and emit warning**

Open `src/piighost/pipeline/base.py`. Find the `__init__` parameter block
near line 153:

```python
        observation_ph_factory: AnyPlaceholderFactory | None = None,
```

This signature is already correct. Now find lines 158-171 in the same
`__init__` (the `obs_ph_factory = observation_ph_factory or RedactPlaceholderFactory()`
block). Replace that block with:

```python
        # Observation redaction is opt-in. None (the default) keeps raw
        # text in observation traces, which is required for downstream
        # HITL dataset extraction. An explicit factory restores the
        # historical redact behaviour but breaks dataset extraction;
        # warn the operator so the trade-off is conscious.
        if observation_ph_factory is not None:
            warnings.warn(
                "observation_ph_factory is set, so observation traces "
                "will be redacted via this factory. With redaction, "
                "the raw user text is no longer recoverable from the "
                "observation backend, which makes traces unsuitable as "
                "input for HITL dataset extraction or NER evaluation. "
                "Pass observation_ph_factory=None (the default) to keep "
                "raw text in traces, or accept the redaction trade-off "
                "if PII must not transit the observation backend.",
                PIIGhostConfigWarning,
                stacklevel=2,
            )
            self._obs_ph_factory: AnyPlaceholderFactory | None = observation_ph_factory
            self._obs_anonymizer: Anonymizer | None = Anonymizer(
                ph_factory=observation_ph_factory
            )
        else:
            self._obs_ph_factory = None
            self._obs_anonymizer = None
```

`PIIGhostConfigWarning` is already imported in this file (used by
`_maybe_warn_unshared_cache` in `pipeline/thread.py`); add the import
at the top of `base.py` if not already present:

```python
from piighost.exceptions import CacheMissError, PIIGhostConfigWarning, PIIRemainingError
```

(It is currently `from piighost.exceptions import CacheMissError, PIIRemainingError` — extend the tuple.)

Also add at the top of the file:

```python
import warnings
```

- [ ] **Step 4: Run the warning test to verify it passes**

Run: `uv run pytest tests/pipeline/test_anon_result_cache.py::TestAnonResultCacheThread::test_explicit_obs_factory_emits_config_warning -v`

Expected: PASS.

- [ ] **Step 5: Add the obs helpers**

Still in `src/piighost/pipeline/base.py`, just below
`_obs_tokens_for_detections` (around the existing line 178 method),
add two new methods:

```python
    def _obs_text(self, text: str, entities: list[Entity]) -> str:
        """Return *text* either raw (no obs factory) or redacted via the obs factory.

        Used to populate the ``input.text`` / ``output.text`` of root and
        child observation spans without leaking raw PII when the operator
        opted into redaction.
        """
        if self._obs_anonymizer is None:
            return text
        return self._obs_anonymizer.anonymize(text, entities)

    def _obs_detection_to_dict(self, d: Detection) -> dict[str, Any]:
        """Render a detection for observation, redacted or raw per config."""
        if self._obs_anonymizer is None:
            return _detection_to_dict(d)
        token_map = self._obs_tokens_for_detections([d])
        return _detection_to_dict(d, token=token_map[d])
```

- [ ] **Step 6: Add the raw-default observation test**

Append to `TestAnonResultCacheThread`:

```python
async def test_default_observation_keeps_raw_text(self) -> None:
    cache = SimpleMemoryCache()
    observation = RecordingObservation()
    detector = CountingDetector([("Patrick", "PERSON")])
    pipeline = ThreadAnonymizationPipeline(
        detector=detector,
        anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
        cache=cache,
        observation=observation,
        # observation_ph_factory omitted -> default None -> raw text
    )

    await pipeline.anonymize("Bonjour Patrick", thread_id="t1")

    anon = [
        (kw, span)
        for kw, span in observation.spans
        if kw.get("name") == "piighost.anonymize_pipeline"
    ]
    assert len(anon) == 1
    _, span = anon[0]
    raw_inputs = [u for u in span.updates if "input" in u]
    assert raw_inputs, "expected at least one input update on the root span"
    assert raw_inputs[0]["input"]["text"] == "Bonjour Patrick"
```

- [ ] **Step 7: Run that test to verify it fails (the helpers exist but
  `_anonymize_with_span` still uses the old direct calls)**

Run: `uv run pytest tests/pipeline/test_anon_result_cache.py::TestAnonResultCacheThread::test_default_observation_keeps_raw_text -v`

Expected: FAIL with the recorded `input.text` still being the redacted
form (the old code path is reached because helpers are not yet wired).

If the test happens to pass already (e.g. the recording observation
doesn't expose this update), proceed; the next task wires helpers
through and a green test there is the real proof.

- [ ] **Step 8: Commit**

```bash
git add src/piighost/pipeline/base.py tests/pipeline/test_anon_result_cache.py
git commit -m "$(cat <<'EOF'
feat(observation)!: default observation_ph_factory to None (raw text)

AnonymizationPipeline.observation_ph_factory used to default to
RedactPlaceholderFactory(), so observation traces always redacted PII
on the way to Langfuse / Opik. This blocks downstream HITL dataset
extraction because the raw user text is unrecoverable. Flip the default
to None: raw text in traces. When the operator passes a factory
explicitly, emit a PIIGhostConfigWarning that documents the trade-off.

Also introduce two helpers, _obs_text and _obs_detection_to_dict,
that centralise the redact-or-not branching so callers in
_anonymize_with_span and override_detections can stay terse. The
helpers are not yet wired in this commit; the next commit threads
them through.

BREAKING CHANGE: observation traces emitted by AnonymizationPipeline
are no longer redacted by default. Pass
observation_ph_factory=RedactPlaceholderFactory() to restore the
prior behaviour.
EOF
)"
```

---

### Task 2: Wire `_obs_text` and `_obs_detection_to_dict` into `pipeline/base.py`'s `_anonymize_with_span`

Replace the direct `_obs_anonymizer.anonymize` and
`_obs_tokens_for_detections + _detection_to_dict(token=...)` calls in
`base.py:_anonymize_with_span` with the two new helpers.

**Files:**
- Modify: `src/piighost/pipeline/base.py`

- [ ] **Step 1: Locate the existing implementation**

In `src/piighost/pipeline/base.py`, find `_anonymize_with_span` (it
starts around line 250). Inside, four call sites use the obs
machinery: detect span (input.text + detections), placeholder span
(input.text), and root span (input.text). Plus the placeholder span
emits `output.text`.

- [ ] **Step 2: Replace the detect span input/output**

Current code, around line 263:

```python
            detections = await self._cached_detect(text)
            det_token_map = self._obs_tokens_for_detections(detections)
            obs_text_pre_link = self._obs_anonymizer.anonymize(
                text, [Entity(detections=(d,)) for d in detections]
            )
            root_span.update(input={"text": obs_text_pre_link})
            span.update(
                input={"text": obs_text_pre_link},
                output={
                    "detections": [
                        _detection_to_dict(d, token=det_token_map[d])
                        for d in detections
                    ]
                },
            )
```

Replace with:

```python
            detections = await self._cached_detect(text)
            obs_text_pre_link = self._obs_text(
                text, [Entity(detections=(d,)) for d in detections]
            )
            root_span.update(input={"text": obs_text_pre_link})
            span.update(
                input={"text": obs_text_pre_link},
                output={
                    "detections": [self._obs_detection_to_dict(d) for d in detections]
                },
            )
```

- [ ] **Step 3: Replace the link span output**

Around line 287, the link span emits entities. Each entity is rendered
with `_entity_to_dict(e, token=ent_tokens[e])` where `ent_tokens` comes
from `self._obs_ph_factory.create(entities)`. With `_obs_ph_factory`
possibly `None`, guard the call:

```python
                ent_tokens = (
                    self._obs_ph_factory.create(entities)
                    if self._obs_ph_factory is not None
                    else {}
                )
                span.update(
                    input={
                        "detections": [
                            self._obs_detection_to_dict(d) for d in detections
                        ]
                    },
                    output={
                        "entities": [
                            _entity_to_dict(
                                e, token=ent_tokens[e] if ent_tokens else None
                            )
                            for e in entities
                        ]
                    },
                )
```

- [ ] **Step 4: Replace the placeholder span input/output**

Around line 305, the placeholder span uses `self._obs_anonymizer.anonymize`:

```python
                obs_text = self._obs_anonymizer.anonymize(text, entities)
                span.update(
                    input={"text": obs_text, "entity_count": len(entities)},
                    output={"text": result},
                )
```

Replace with:

```python
                obs_text = self._obs_text(text, entities)
                span.update(
                    input={"text": obs_text, "entity_count": len(entities)},
                    output={"text": result},
                )
```

- [ ] **Step 5: Run the raw-default observation test from Task 1**

Run: `uv run pytest tests/pipeline/test_anon_result_cache.py::TestAnonResultCacheThread::test_default_observation_keeps_raw_text -v`

Expected: PASS — the recorded input.text is now `"Bonjour Patrick"`
(raw) because the obs factory is `None`.

- [ ] **Step 6: Run the full test file to catch regressions**

Run: `uv run pytest tests/pipeline/test_anon_result_cache.py -v`

Expected: every test passes. If any tests fail because they expected
redaction and now see raw text, update those assertions to expect
raw.

- [ ] **Step 7: Commit**

```bash
git add src/piighost/pipeline/base.py
git commit -m "feat(observation): wire _obs_text and _obs_detection_to_dict into base pipeline"
```

---

### Task 3: Wire helpers into `pipeline/thread.py` and update HITL test assertions

The `ThreadAnonymizationPipeline` overrides `_anonymize_with_span` and
also calls obs machinery from `override_detections`. Both must use the
new helpers. The existing HITL test asserts `text != "Patrick"` (i.e.
text is redacted); flip the assertions to expect raw text.

**Files:**
- Modify: `src/piighost/pipeline/thread.py`
- Modify: `tests/pipeline/test_anon_result_cache.py`

- [ ] **Step 1: Update `_anonymize_with_span` in `thread.py`**

In `src/piighost/pipeline/thread.py`, find `_anonymize_with_span`
(starts around line 581). The same four call sites exist. Apply the
exact same replacements as in Task 2: substitute
`self._obs_anonymizer.anonymize` with `self._obs_text`, replace
`_detection_to_dict(d, token=det_token_map[d])` with
`self._obs_detection_to_dict(d)`, guard `_obs_ph_factory.create` with
a `None` check (use `{}` fallback for the token map).

- [ ] **Step 2: Update `override_detections` in `thread.py`**

Find `override_detections` (around line 374). Inside the `try` block,
replace this code:

```python
                before_tokens = self._obs_tokens_for_detections(before)
                after_tokens = self._obs_tokens_for_detections(detections)
                detector_labels = getattr(self._detector, "labels", None)
                span.update(
                    input={
                        "text": text,
                        "labels": list(detector_labels) if detector_labels else [],
                        "detections": [
                            _detection_to_dict(d, token=before_tokens[d])
                            for d in before
                        ],
                    },
                    output={
                        "detections": [
                            _detection_to_dict(d, token=after_tokens[d])
                            for d in detections
                        ]
                    },
                )
```

With:

```python
                detector_labels = getattr(self._detector, "labels", None)
                span.update(
                    input={
                        "text": text,
                        "labels": list(detector_labels) if detector_labels else [],
                        "detections": [
                            self._obs_detection_to_dict(d) for d in before
                        ],
                    },
                    output={
                        "detections": [
                            self._obs_detection_to_dict(d) for d in detections
                        ]
                    },
                )
```

- [ ] **Step 3: Update the existing HITL redacted-diff test**

In `tests/pipeline/test_anon_result_cache.py`, find
`test_override_detections_emits_hitl_span_with_redacted_diff` (around
line 277). Replace the lines that assert text is redacted with raw
expectations:

Find:
```python
        # Text is redacted by the default observation factory (RedactPlaceholderFactory),
        # independent of the user-facing LabelCounterPlaceholderFactory configured above.
        assert update["input"]["detections"][0]["text"] != "Patrick"
        assert update["output"]["detections"][0]["text"] != "Patrick"
```

Replace with:
```python
        # observation_ph_factory defaults to None now, so detection text
        # is the raw user input. The user-facing LabelCounterPlaceholderFactory
        # is unrelated to observation redaction.
        assert update["input"]["detections"][0]["text"] == "Patrick"
        assert update["output"]["detections"][0]["text"] == "Patrick"
```

Rename the test to drop the misleading `_with_redacted_diff` suffix:

Find:
```python
    async def test_override_detections_emits_hitl_span_with_redacted_diff(self) -> None:
```

Replace with:
```python
    async def test_override_detections_emits_hitl_span_with_diff(self) -> None:
```

- [ ] **Step 4: Add an explicit-factory HITL test that asserts redaction still works**

Append to `TestAnonResultCacheThread`:

```python
async def test_override_detections_with_obs_factory_redacts(self) -> None:
    import warnings

    from piighost.exceptions import PIIGhostConfigWarning
    from piighost.placeholder import RedactPlaceholderFactory

    cache = SimpleMemoryCache()
    observation = RecordingObservation()
    detector = CountingDetector([("Patrick", "PERSON")])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PIIGhostConfigWarning)
        pipeline = ThreadAnonymizationPipeline(
            detector=detector,
            anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
            cache=cache,
            observation=observation,
            observation_ph_factory=RedactPlaceholderFactory(),
        )

    await pipeline.anonymize("Bonjour Patrick", thread_id="t1")
    corrected = [
        Detection(
            text="Patrick",
            label="ORG",
            position=Span(start_pos=8, end_pos=15),
            confidence=1.0,
        )
    ]
    await pipeline.override_detections("Bonjour Patrick", corrected, thread_id="t1")

    hitl = [
        (kw, span)
        for kw, span in observation.spans
        if kw.get("name") == "piighost.hitl_correction"
    ]
    assert len(hitl) == 1
    _, span = hitl[0]
    update = span.updates[0]
    # input.text stays raw (same as before): the HITL trace always
    # carries the raw text so the dataset stays extractable. But
    # detection.text is redacted because the explicit factory is set.
    assert update["input"]["text"] == "Bonjour Patrick"
    assert update["input"]["detections"][0]["text"] != "Patrick"
    assert update["output"]["detections"][0]["text"] != "Patrick"
```

- [ ] **Step 5: Run the full test file**

Run: `uv run pytest tests/pipeline/test_anon_result_cache.py -v`

Expected: every test passes (15 tests now: original 13 + warning + raw-default + explicit-factory).

- [ ] **Step 6: Commit**

```bash
git add src/piighost/pipeline/thread.py tests/pipeline/test_anon_result_cache.py
git commit -m "feat(observation): wire helpers into ThreadAnonymizationPipeline"
```

---

### Task 4: Delete the example PEP 723 scripts

The CLI in piighost-api supersedes them. Drop them so users don't keep
two ways of doing the same thing.

**Files:**
- Delete: `examples/observation/export_hitl_dataset.py`
- Delete: `examples/observation/compute_hitl_metrics.py`

- [ ] **Step 1: Verify the files exist before deleting**

Run: `ls examples/observation/`

Expected output includes `export_hitl_dataset.py` and `compute_hitl_metrics.py`.

- [ ] **Step 2: Delete both files**

Run:

```bash
git rm examples/observation/export_hitl_dataset.py examples/observation/compute_hitl_metrics.py
```

- [ ] **Step 3: Verify the test suite still passes (sanity, no test imports the scripts)**

Run: `uv run pytest tests/`

Expected: every test passes.

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
chore(examples): drop PEP 723 HITL scripts in favour of piighost-api CLI

export_hitl_dataset.py and compute_hitl_metrics.py are replaced by
``piighost-api dataset extract`` and ``piighost-api dataset metrics``.
The CLI lives in piighost-api because it consumes the same Langfuse
credentials and runs operationally next to the inference server.
EOF
)"
```

---

## Phase 2 — piighost-api CLI

Switch to the piighost-api repo: `cd ~/PycharmProjects/piighost-api`.
All file paths in Phase 2 are relative to that repo root.

### Task 5: Add typer + dataset extra to `pyproject.toml`

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Open `pyproject.toml` and locate the dependency block**

The current state has these around lines 31-43:

```toml
dependencies = [
    "piighost>=0.10",
    "keyshield[argon2]>=2.0",
    "litestar>=2.16",
    "uvicorn>=0.34",
    "aiocache>=0.12",
    "msgspec>=0.19",
    "requests>=2.32",
]

[project.optional-dependencies]
langfuse = ["piighost[langfuse]"]
opik = ["piighost[opik]"]
```

- [ ] **Step 2: Add typer to base dependencies and a `dataset` extra**

Replace those blocks with:

```toml
dependencies = [
    "piighost>=0.10",
    "keyshield[argon2]>=2.0",
    "litestar>=2.16",
    "uvicorn>=0.34",
    "aiocache>=0.12",
    "msgspec>=0.19",
    "requests>=2.32",
    "typer>=0.12",
]

[project.optional-dependencies]
langfuse = ["piighost[langfuse]"]
opik = ["piighost[opik]"]
# Marker-only extra: enables the editable local piighost source declared
# in [tool.uv.sources]. Use `uv sync --extra dev-local` to consume the
# sibling piighost checkout instead of the published wheel.
dev-local = []
# Dataset CLI dependencies. Pulls the Langfuse SDK so the
# `piighost-api dataset extract` command can talk to the observation
# backend directly.
dataset = ["langfuse>=3.0"]
```

(Preserve any existing `dev-local` extra block already there.)

- [ ] **Step 3: Sync the lockfile**

Run: `uv sync --extra dataset`

Expected: lockfile updated to include typer and langfuse. No other
churn.

- [ ] **Step 4: Run the existing test suite to confirm nothing else broke**

Run: `uv run pytest -q`

Expected: every test passes.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat(deps): add typer base dep and dataset extra (langfuse SDK)"
```

---

### Task 6: Create `dataset/extract.py` with extraction primitives + tests

Pure functions that take a Langfuse client (or anything quack-typed),
fetch traces, and yield JSONL records. The CLI module wires them.

**Files:**
- Create: `src/piighost_api/dataset/__init__.py`
- Create: `src/piighost_api/dataset/extract.py`
- Create: `tests/test_dataset_extract.py`

- [ ] **Step 1: Create the package init**

Create `src/piighost_api/dataset/__init__.py` with:

```python
"""Dataset CLI helpers: extract Langfuse traces, compute NER metrics."""
```

- [ ] **Step 2: Write the failing tests for record shaping**

Create `tests/test_dataset_extract.py`:

```python
"""Tests for the Langfuse trace -> JSONL record shaping."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any

from piighost_api.dataset.extract import (
    DatasetMode,
    record_from_trace,
)


def _trace(
    *,
    name: str,
    input: dict[str, Any] | None,
    output: dict[str, Any] | None,
    trace_id: str = "tid",
    session_id: str | None = "session",
    created_at: str | None = "2026-05-01T05:47:27.000Z",
    observations: list[Any] | None = None,
) -> Any:
    return SimpleNamespace(
        name=name,
        input=input,
        output=output,
        id=trace_id,
        session_id=session_id,
        createdAt=created_at,
        observations=observations or [],
    )


def test_hitl_trace_yields_record_with_human_entities() -> None:
    trace = _trace(
        name="piighost.hitl_correction",
        input={
            "text": "Bonjour Patrick",
            "labels": ["PERSON"],
            "detections": [
                {"label": "PERSON", "position": [8, 15], "confidence": 0.4, "text": "Patrick"}
            ],
        },
        output={
            "detections": [
                {"label": "ORG", "position": [8, 15], "confidence": 1.0, "text": "Patrick"}
            ]
        },
    )

    record = record_from_trace(trace, mode=DatasetMode.all)

    assert record is not None
    assert record["text"] == "Bonjour Patrick"
    assert record["entities"] == [[8, 15, "ORG"]]
    assert record["model_entities"] == [[8, 15, "PERSON"]]
    assert record["labels_universe"] == ["PERSON"]
    assert record["source"] == "hitl"
    assert record["trace_id"] == "tid"
    assert record["session_id"] == "session"


def test_anonymize_trace_yields_model_only_record() -> None:
    detect_obs = SimpleNamespace(
        name="piighost.detect",
        output={
            "detections": [
                {"label": "PERSON", "position": [8, 15], "confidence": 0.9}
            ]
        },
    )
    trace = _trace(
        name="piighost.anonymize_pipeline",
        input={"text": "Bonjour Patrick"},
        output={"text": "Bonjour <<PERSON:1>>", "entity_count": 1},
        observations=[detect_obs],
    )

    record = record_from_trace(trace, mode=DatasetMode.all)

    assert record is not None
    assert record["text"] == "Bonjour Patrick"
    assert record["entities"] == [[8, 15, "PERSON"]]
    assert record["model_entities"] == [[8, 15, "PERSON"]]
    assert record["source"] == "model"


def test_trace_without_input_text_is_skipped() -> None:
    trace = _trace(
        name="piighost.hitl_correction",
        input={"detections": []},
        output={"detections": []},
    )

    assert record_from_trace(trace, mode=DatasetMode.all) is None


def test_mode_hitl_skips_anonymize_traces() -> None:
    trace = _trace(
        name="piighost.anonymize_pipeline",
        input={"text": "Bonjour"},
        output={"text": "Bonjour", "entity_count": 0},
        observations=[],
    )
    assert record_from_trace(trace, mode=DatasetMode.hitl) is None


def test_mode_model_only_skips_hitl_traces() -> None:
    trace = _trace(
        name="piighost.hitl_correction",
        input={"text": "Bonjour", "detections": []},
        output={"detections": []},
    )
    assert record_from_trace(trace, mode=DatasetMode.model_only) is None
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_dataset_extract.py -v`

Expected: FAIL — `piighost_api.dataset.extract` does not exist yet.

- [ ] **Step 4: Implement `extract.py`**

Create `src/piighost_api/dataset/extract.py`:

```python
"""Pure extraction logic: Langfuse trace -> JSONL record dict.

The CLI module wires these functions to a real Langfuse client and
writes the records to disk. The functions in this module take
quack-typed objects (anything with the right attributes / keys) so
tests can drive them with simple namespaces.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class DatasetMode(str, Enum):
    """Which Langfuse trace types end up in the dataset."""

    all = "all"
    hitl = "hitl"
    model_only = "model-only"


HITL_TRACE_NAME = "piighost.hitl_correction"
ANONYMIZE_TRACE_NAME = "piighost.anonymize_pipeline"
DETECT_OBS_NAME = "piighost.detect"


def _entities_from_detections(detections: list[dict[str, Any]] | None) -> list[list[Any]]:
    """Convert a list of detection dicts into ``[[start, end, label], ...]``."""
    if not detections:
        return []
    out: list[list[Any]] = []
    for det in detections:
        position = det.get("position") or [det.get("start_pos"), det.get("end_pos")]
        if position is None or position[0] is None or position[1] is None:
            continue
        label = det.get("label")
        if label is None:
            continue
        out.append([int(position[0]), int(position[1]), str(label)])
    return out


def _detect_obs_for(trace: Any) -> Any | None:
    """Return the ``piighost.detect`` child observation from *trace*, or None."""
    observations = getattr(trace, "observations", None) or []
    for obs in observations:
        if getattr(obs, "name", None) == DETECT_OBS_NAME:
            return obs
    return None


def record_from_trace(trace: Any, *, mode: DatasetMode) -> dict[str, Any] | None:
    """Build a JSONL record from a Langfuse trace, or ``None`` if it should be skipped.

    A trace is skipped when:

    * its ``name`` does not match the active ``mode``,
    * its ``input.text`` is missing or empty (older traces predate the
      raw-text-by-default lib change),
    * for ``model-only`` records, its ``piighost.detect`` child
      observation is missing.
    """
    name = getattr(trace, "name", None)
    if mode is DatasetMode.hitl and name != HITL_TRACE_NAME:
        return None
    if mode is DatasetMode.model_only and name != ANONYMIZE_TRACE_NAME:
        return None
    if name not in (HITL_TRACE_NAME, ANONYMIZE_TRACE_NAME):
        return None

    raw_input = getattr(trace, "input", None) or {}
    if not isinstance(raw_input, dict):
        return None
    text = raw_input.get("text")
    if not isinstance(text, str) or not text:
        return None

    if name == HITL_TRACE_NAME:
        raw_output = getattr(trace, "output", None) or {}
        if not isinstance(raw_output, dict):
            return None
        human_entities = _entities_from_detections(raw_output.get("detections"))
        model_entities = _entities_from_detections(raw_input.get("detections"))
        labels_universe = list(raw_input.get("labels") or [])
        source = "hitl"
        entities = human_entities
    else:
        detect_obs = _detect_obs_for(trace)
        if detect_obs is None:
            return None
        detect_output = getattr(detect_obs, "output", None) or {}
        if not isinstance(detect_output, dict):
            return None
        model_entities = _entities_from_detections(detect_output.get("detections"))
        human_entities = list(model_entities)
        labels_universe = []
        source = "model"
        entities = human_entities

    return {
        "text": text,
        "entities": entities,
        "model_entities": model_entities,
        "labels_universe": labels_universe,
        "source": source,
        "trace_id": getattr(trace, "id", None),
        "session_id": getattr(trace, "session_id", None),
        "created_at": getattr(trace, "createdAt", None),
    }
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_dataset_extract.py -v`

Expected: PASS — five tests green.

- [ ] **Step 6: Commit**

```bash
git add src/piighost_api/dataset/__init__.py src/piighost_api/dataset/extract.py tests/test_dataset_extract.py
git commit -m "feat(dataset): add Langfuse trace -> JSONL record shaping"
```

---

### Task 7: Create `dataset/metrics.py` with metrics primitives + tests

Port the algorithms from the (now deleted) `compute_hitl_metrics.py`,
add a `--source` filter, expose pure functions and the table / CSV /
JSON renderers.

**Files:**
- Create: `src/piighost_api/dataset/metrics.py`
- Create: `tests/test_dataset_metrics.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_dataset_metrics.py`:

```python
"""Tests for the metrics computation: aggregation + source filtering."""

from __future__ import annotations

from piighost_api.dataset.metrics import (
    LabelStats,
    MatchMode,
    SourceFilter,
    aggregate,
)


HITL_RECORD = {
    "text": "Bonjour Patrick",
    "entities": [[8, 15, "PERSON"]],
    "model_entities": [[8, 15, "ORG"]],
    "labels_universe": ["PERSON"],
    "source": "hitl",
    "trace_id": "h1",
    "session_id": "s1",
    "created_at": "2026-05-01T00:00:00Z",
}

MODEL_RECORD = {
    "text": "Hello John",
    "entities": [[6, 10, "PERSON"]],
    "model_entities": [[6, 10, "PERSON"]],
    "labels_universe": [],
    "source": "model",
    "trace_id": "m1",
    "session_id": "s2",
    "created_at": "2026-05-01T00:01:00Z",
}


def test_strict_match_counts_tp_fp_fn_per_label() -> None:
    per_label, _ = aggregate(
        [HITL_RECORD, MODEL_RECORD],
        match_mode=MatchMode.strict,
        source_filter=SourceFilter.all,
    )

    # HITL record: model said ORG @ 8-15, human said PERSON @ 8-15.
    # That's a label-changed: ORG counts as fp, PERSON as fn.
    # MODEL record: model == human => PERSON tp.
    assert per_label["PERSON"].tp == 1
    assert per_label["PERSON"].fn == 1
    assert per_label["ORG"].fp == 1
    assert per_label["ORG"].tp == 0


def test_label_changed_records_a_confusion_pair() -> None:
    _, confusion = aggregate(
        [HITL_RECORD],
        match_mode=MatchMode.strict,
        source_filter=SourceFilter.all,
    )
    assert confusion[("ORG", "PERSON")] == 1


def test_source_filter_hitl_excludes_model_record() -> None:
    per_label, _ = aggregate(
        [HITL_RECORD, MODEL_RECORD],
        match_mode=MatchMode.strict,
        source_filter=SourceFilter.hitl,
    )
    # The MODEL record should not show up (it would have produced PERSON tp).
    assert per_label["PERSON"].tp == 0
    assert per_label["PERSON"].fn == 1
    assert per_label["ORG"].fp == 1


def test_source_filter_model_excludes_hitl_record() -> None:
    per_label, confusion = aggregate(
        [HITL_RECORD, MODEL_RECORD],
        match_mode=MatchMode.strict,
        source_filter=SourceFilter.model,
    )
    assert per_label["PERSON"].tp == 1
    assert per_label["PERSON"].fn == 0
    assert "ORG" not in per_label
    assert confusion == {}


def test_label_stats_precision_recall_f1() -> None:
    s = LabelStats(tp=3, fp=1, fn=2)
    assert s.precision == 3 / 4
    assert s.recall == 3 / 5
    assert abs(s.f1 - (2 * (3 / 4) * (3 / 5) / ((3 / 4) + (3 / 5)))) < 1e-9
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_dataset_metrics.py -v`

Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `metrics.py`**

Create `src/piighost_api/dataset/metrics.py`:

```python
"""Pure metrics computation over a HITL JSONL dataset.

Aggregates per-label TP / FP / FN with strict or lenient (IoU)
matching, surfaces a label-confusion matrix for spans where model and
human disagree on the label, and supports filtering by record source
(``hitl``, ``model``, ``all``).
"""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any


class MatchMode(str, Enum):
    strict = "strict"
    lenient = "lenient"


class SourceFilter(str, Enum):
    all = "all"
    hitl = "hitl"
    model = "model"


class OutputFormat(str, Enum):
    table = "table"
    csv = "csv"
    json = "json"


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    label: str

    def iou(self, other: "Span") -> float:
        inter_start = max(self.start, other.start)
        inter_end = min(self.end, other.end)
        inter = max(0, inter_end - inter_start)
        union = max(self.end, other.end) - min(self.start, other.start)
        return inter / union if union > 0 else 0.0


@dataclass
class LabelStats:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        d = self.tp + self.fp
        return self.tp / d if d else 0.0

    @property
    def recall(self) -> float:
        d = self.tp + self.fn
        return self.tp / d if d else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


def _parse(items: list[list[Any]] | None) -> list[Span]:
    if not items:
        return []
    out: list[Span] = []
    for item in items:
        if len(item) < 3 or item[2] is None:
            continue
        out.append(Span(int(item[0]), int(item[1]), str(item[2])))
    return out


def _match_strict(
    model: list[Span], human: list[Span]
) -> tuple[list[tuple[Span, Span]], list[Span], list[Span]]:
    keyed = {(s.start, s.end, s.label): s for s in human}
    matches: list[tuple[Span, Span]] = []
    model_only: list[Span] = []
    consumed: set[tuple[int, int, str]] = set()
    for m in model:
        key = (m.start, m.end, m.label)
        if key in keyed and key not in consumed:
            matches.append((m, keyed[key]))
            consumed.add(key)
        else:
            model_only.append(m)
    human_only = [h for h in human if (h.start, h.end, h.label) not in consumed]
    return matches, model_only, human_only


def _match_lenient(
    model: list[Span], human: list[Span], iou_threshold: float
) -> tuple[list[tuple[Span, Span]], list[Span], list[Span]]:
    pairs: list[tuple[float, int, int]] = []
    for i, m in enumerate(model):
        for j, h in enumerate(human):
            if m.label != h.label:
                continue
            score = m.iou(h)
            if score >= iou_threshold:
                pairs.append((score, i, j))
    pairs.sort(reverse=True)

    matched_model: set[int] = set()
    matched_human: set[int] = set()
    matches: list[tuple[Span, Span]] = []
    for _, i, j in pairs:
        if i in matched_model or j in matched_human:
            continue
        matches.append((model[i], human[j]))
        matched_model.add(i)
        matched_human.add(j)
    model_only = [m for i, m in enumerate(model) if i not in matched_model]
    human_only = [h for j, h in enumerate(human) if j not in matched_human]
    return matches, model_only, human_only


def aggregate(
    records: list[dict[str, Any]],
    *,
    match_mode: MatchMode = MatchMode.strict,
    source_filter: SourceFilter = SourceFilter.all,
    iou_threshold: float = 0.5,
) -> tuple[dict[str, LabelStats], dict[tuple[str, str], int]]:
    per_label: dict[str, LabelStats] = defaultdict(LabelStats)
    confusion: dict[tuple[str, str], int] = defaultdict(int)

    for rec in records:
        if source_filter is not SourceFilter.all:
            if rec.get("source") != source_filter.value:
                continue
        model = _parse(rec.get("model_entities"))
        human = _parse(rec.get("entities"))

        if match_mode is MatchMode.strict:
            matches, model_only, human_only = _match_strict(model, human)
        else:
            matches, model_only, human_only = _match_lenient(model, human, iou_threshold)

        for m, _ in matches:
            per_label[m.label].tp += 1
        for m in model_only:
            same_span = next(
                (h for h in human_only if h.start == m.start and h.end == m.end),
                None,
            )
            if same_span is not None:
                confusion[(m.label, same_span.label)] += 1
            per_label[m.label].fp += 1
        for h in human_only:
            per_label[h.label].fn += 1

    return dict(per_label), dict(confusion)


def macro_avg(per_label: dict[str, LabelStats]) -> dict[str, float]:
    if not per_label:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    n = len(per_label)
    return {
        "precision": sum(s.precision for s in per_label.values()) / n,
        "recall": sum(s.recall for s in per_label.values()) / n,
        "f1": sum(s.f1 for s in per_label.values()) / n,
    }


def micro_avg(per_label: dict[str, LabelStats]) -> dict[str, float]:
    tp = sum(s.tp for s in per_label.values())
    fp = sum(s.fp for s in per_label.values())
    fn = sum(s.fn for s in per_label.values())
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"precision": p, "recall": r, "f1": f1}


def render_table(
    per_label: dict[str, LabelStats], confusion: dict[tuple[str, str], int]
) -> str:
    if not per_label:
        return "(no records)"
    header = f"{'label':<20s} {'tp':>6} {'fp':>6} {'fn':>6} {'P':>6} {'R':>6} {'F1':>6}"
    sep = "-" * len(header)
    lines = [header, sep]
    for label in sorted(per_label):
        s = per_label[label]
        lines.append(
            f"{label:<20s} {s.tp:>6d} {s.fp:>6d} {s.fn:>6d}"
            f" {s.precision:>6.2f} {s.recall:>6.2f} {s.f1:>6.2f}"
        )
    lines.append(sep)
    macro = macro_avg(per_label)
    micro = micro_avg(per_label)
    lines.append(
        f"{'macro avg':<20s} {'-':>6} {'-':>6} {'-':>6}"
        f" {macro['precision']:>6.2f} {macro['recall']:>6.2f} {macro['f1']:>6.2f}"
    )
    lines.append(
        f"{'micro avg':<20s} {'-':>6} {'-':>6} {'-':>6}"
        f" {micro['precision']:>6.2f} {micro['recall']:>6.2f} {micro['f1']:>6.2f}"
    )
    if confusion:
        lines.append("")
        lines.append("Label confusion (model -> human, same span):")
        for (m, h), n in sorted(confusion.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {m} -> {h}: {n}")
    return "\n".join(lines)


def render_csv(per_label: dict[str, LabelStats]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["label", "tp", "fp", "fn", "precision", "recall", "f1"])
    for label in sorted(per_label):
        s = per_label[label]
        w.writerow(
            [label, s.tp, s.fp, s.fn, f"{s.precision:.4f}", f"{s.recall:.4f}", f"{s.f1:.4f}"]
        )
    macro = macro_avg(per_label)
    micro = micro_avg(per_label)
    w.writerow([])
    w.writerow(
        [
            "macro avg",
            "",
            "",
            "",
            f"{macro['precision']:.4f}",
            f"{macro['recall']:.4f}",
            f"{macro['f1']:.4f}",
        ]
    )
    w.writerow(
        [
            "micro avg",
            "",
            "",
            "",
            f"{micro['precision']:.4f}",
            f"{micro['recall']:.4f}",
            f"{micro['f1']:.4f}",
        ]
    )
    return buf.getvalue()


def render_json(
    per_label: dict[str, LabelStats], confusion: dict[tuple[str, str], int]
) -> str:
    nested: dict[str, dict[str, int]] = defaultdict(dict)
    for (m, h), n in confusion.items():
        nested[m][h] = n
    payload = {
        "per_label": {
            label: {
                "tp": s.tp,
                "fp": s.fp,
                "fn": s.fn,
                "precision": s.precision,
                "recall": s.recall,
                "f1": s.f1,
            }
            for label, s in per_label.items()
        },
        "macro_avg": macro_avg(per_label),
        "micro_avg": micro_avg(per_label),
        "label_confusion": dict(nested),
    }
    return json.dumps(payload, indent=2)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_dataset_metrics.py -v`

Expected: PASS — five tests green.

- [ ] **Step 5: Commit**

```bash
git add src/piighost_api/dataset/metrics.py tests/test_dataset_metrics.py
git commit -m "feat(dataset): add JSONL -> per-label P/R/F1 metrics primitives"
```

---

### Task 8: Migrate `cli.py` to Typer with `serve` + `dataset extract` + `dataset metrics`

Replace argparse with a Typer app. Preserve the existing
`_create_app` pattern so uvicorn keeps using a factory.

**Files:**
- Modify: `src/piighost_api/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Replace `cli.py` content**

Replace the whole contents of `src/piighost_api/cli.py` with:

```python
"""Typer CLI entrypoint for piighost-api.

Subcommands:
* ``serve``: start the API server (existing behaviour).
* ``dataset extract``: pull HITL / model traces from Langfuse into a
  JSONL training dataset.
* ``dataset metrics``: compute per-label P/R/F1 on a JSONL dataset.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import typer
import uvicorn

from piighost_api.dataset.extract import (
    ANONYMIZE_TRACE_NAME,
    HITL_TRACE_NAME,
    DatasetMode,
    record_from_trace,
)
from piighost_api.dataset.metrics import (
    MatchMode,
    OutputFormat,
    SourceFilter,
    aggregate,
    render_csv,
    render_json,
    render_table,
)


app = typer.Typer(no_args_is_help=True, add_completion=False)
dataset_app = typer.Typer(no_args_is_help=True, help="HITL dataset operations.")
app.add_typer(dataset_app, name="dataset")


@app.command()
def serve(
    pipeline: str = typer.Argument(
        ..., help="Pipeline import path in module:variable format."
    ),
    host: str = typer.Option("127.0.0.1", help="Bind host."),
    port: int = typer.Option(8000, help="Bind port."),
    log_level: str = typer.Option(
        "info", help="Log level (debug | info | warning | error)."
    ),
) -> None:
    """Start the API server."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    os.environ["PIIGHOST_PIPELINE"] = pipeline
    uvicorn.run(
        "piighost_api.cli:_create_app",
        factory=True,
        host=host,
        port=port,
        log_level=log_level,
    )


@dataset_app.command("extract")
def dataset_extract(
    output: Path = typer.Option(..., "--output", "-o", help="JSONL file to write."),
    since: datetime | None = typer.Option(
        None, "--since", help="Skip traces older than this ISO timestamp."
    ),
    until: datetime | None = typer.Option(
        None, "--until", help="Skip traces newer than this ISO timestamp."
    ),
    mode: DatasetMode = typer.Option(DatasetMode.all, "--mode"),
    limit: int | None = typer.Option(
        None, "--limit", help="Stop after N records."
    ),
) -> None:
    """Extract HITL + non-HITL traces from Langfuse into a JSONL dataset."""
    if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
        typer.echo(
            "Missing LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY. "
            "Set them with the keys from your Langfuse project settings.",
            err=True,
        )
        raise typer.Exit(code=1)

    from langfuse import Langfuse  # imported lazily so `--help` works without the extra

    client = Langfuse()
    fetch_kwargs: dict = {}
    if since is not None:
        fetch_kwargs["from_timestamp"] = since
    if until is not None:
        fetch_kwargs["to_timestamp"] = until

    names_to_fetch = []
    if mode in (DatasetMode.all, DatasetMode.hitl):
        names_to_fetch.append(HITL_TRACE_NAME)
    if mode in (DatasetMode.all, DatasetMode.model_only):
        names_to_fetch.append(ANONYMIZE_TRACE_NAME)

    written = 0
    skipped = 0
    with output.open("w", encoding="utf-8") as fh:
        for name in names_to_fetch:
            traces = client.api.trace.list(name=name, **fetch_kwargs).data
            for trace in traces:
                if name == ANONYMIZE_TRACE_NAME:
                    full = client.api.trace.get(trace.id)
                    record = record_from_trace(full, mode=mode)
                else:
                    record = record_from_trace(trace, mode=mode)
                if record is None:
                    skipped += 1
                    continue
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                written += 1
                if limit is not None and written >= limit:
                    break
            if limit is not None and written >= limit:
                break

    typer.echo(f"Wrote {written} records to {output} ({skipped} skipped).")


@dataset_app.command("metrics")
def dataset_metrics(
    input: Path = typer.Option(..., "--input", "-i", help="JSONL file to read."),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write the report to this path instead of stdout."
    ),
    output_format: OutputFormat = typer.Option(OutputFormat.table, "--output-format"),
    match_mode: MatchMode = typer.Option(MatchMode.strict, "--match-mode"),
    iou_threshold: float = typer.Option(
        0.5, "--iou-threshold", help="Span-IoU floor in lenient mode."
    ),
    source: SourceFilter = typer.Option(
        SourceFilter.all, "--source", help="Restrict aggregation to one record source."
    ),
) -> None:
    """Compute per-label P/R/F1 from a HITL JSONL dataset."""
    records = []
    with input.open(encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))

    per_label, confusion = aggregate(
        records,
        match_mode=match_mode,
        source_filter=source,
        iou_threshold=iou_threshold,
    )

    if output_format is OutputFormat.table:
        out = render_table(per_label, confusion)
    elif output_format is OutputFormat.csv:
        out = render_csv(per_label)
    else:
        out = render_json(per_label, confusion)

    if output is None:
        typer.echo(out)
    else:
        output.write_text(out, encoding="utf-8")


def _create_app():
    """App factory called by uvicorn (preserved from the argparse CLI)."""
    from piighost_api.app import create_app

    pipeline_path = os.environ["PIIGHOST_PIPELINE"]
    return create_app(pipeline_path)


def main() -> None:
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
```

- [ ] **Step 2: Replace `tests/test_cli.py` with Typer-friendly tests**

Replace the whole contents of `tests/test_cli.py` with:

```python
"""Tests for cli.py — Typer-based multi-subcommand entrypoint."""

import os
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from piighost_api.cli import _create_app, app


runner = CliRunner()


def test_no_command_prints_help_and_exits_zero() -> None:
    result = runner.invoke(app, [])
    # Typer with no_args_is_help=True returns 0 and prints the help banner.
    assert result.exit_code == 0
    assert "Usage" in result.stdout


def test_serve_sets_env_and_runs_uvicorn() -> None:
    with patch("piighost_api.cli.uvicorn") as mock_uvicorn:
        result = runner.invoke(
            app,
            [
                "serve",
                "mymod:pipe",
                "--host",
                "0.0.0.0",
                "--port",
                "9000",
                "--log-level",
                "debug",
            ],
        )

    assert result.exit_code == 0
    assert os.environ["PIIGHOST_PIPELINE"] == "mymod:pipe"
    mock_uvicorn.run.assert_called_once_with(
        "piighost_api.cli:_create_app",
        factory=True,
        host="0.0.0.0",
        port=9000,
        log_level="debug",
    )


def test_dataset_extract_help() -> None:
    result = runner.invoke(app, ["dataset", "extract", "--help"])
    assert result.exit_code == 0
    assert "--output" in result.stdout
    assert "--since" in result.stdout
    assert "--mode" in result.stdout


def test_dataset_metrics_help() -> None:
    result = runner.invoke(app, ["dataset", "metrics", "--help"])
    assert result.exit_code == 0
    assert "--input" in result.stdout
    assert "--match-mode" in result.stdout
    assert "--source" in result.stdout


def test_dataset_extract_missing_credentials_exits_one() -> None:
    with patch.dict(os.environ, {}, clear=True):
        result = runner.invoke(
            app, ["dataset", "extract", "--output", "/tmp/should-not-exist.jsonl"]
        )
    assert result.exit_code == 1
    assert "LANGFUSE_PUBLIC_KEY" in result.stderr or "LANGFUSE_PUBLIC_KEY" in result.stdout


def test_create_app_factory() -> None:
    with patch.dict(os.environ, {"PIIGHOST_PIPELINE": "test:pipeline"}):
        with patch("piighost_api.app.create_app") as mock_create:
            mock_create.return_value = MagicMock()
            result = _create_app()
            mock_create.assert_called_once_with("test:pipeline")
            assert result is mock_create.return_value
```

- [ ] **Step 3: Run the new CLI tests**

Run: `uv run pytest tests/test_cli.py -v`

Expected: PASS for all six tests.

If `test_dataset_extract_missing_credentials_exits_one` fails because
`runner.invoke` returns a different exit code, inspect `result.exception`
to see if Typer is raising before the env-var check; tighten the test
accordingly (for example by patching `sys.exit` or checking
`result.exit_code != 0`).

- [ ] **Step 4: Run the full repo test suite**

Run: `uv run pytest -q`

Expected: every test passes.

- [ ] **Step 5: Commit**

```bash
git add src/piighost_api/cli.py tests/test_cli.py
git commit -m "feat(cli): migrate to Typer and add 'dataset extract|metrics' subcommands"
```

---

### Task 9: Final verification

**Files:** none modified — verification only.

- [ ] **Step 1: Run the whole repo test suite**

Run: `uv run pytest`

Expected: every test passes.

- [ ] **Step 2: Run `make lint`**

Run: `make lint`

Expected: ruff format / ruff check / pyrefly all return clean. Apply
`uv run ruff format` if format reports unformatted files. Pyrefly
errors that exist on the base SHA before this work started are
acceptable; new errors introduced by this work are not.

- [ ] **Step 3: Smoke test the CLI**

Confirm that the help banner is reachable without Langfuse creds:

```bash
uv run piighost-api --help
uv run piighost-api dataset --help
uv run piighost-api dataset extract --help
uv run piighost-api dataset metrics --help
```

Expected: each prints a usage banner with the documented options.

- [ ] **Step 4: End-to-end smoke test against the running stack**

If the chat stack is up (`cd ~/PycharmProjects/piighost-chat && make docker-up-local`), pick the export commands the user actually runs:

```bash
unset VIRTUAL_ENV
set -a && source .env && set +a
uv run piighost-api dataset extract \
    --output /tmp/dataset.jsonl \
    --since "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S)"
uv run piighost-api dataset metrics --input /tmp/dataset.jsonl
```

Expected: extract reports a count, metrics print a table with the
records that landed via the chat UI.

- [ ] **Step 5: Sanity-check the spec**

Open `docs/superpowers/specs/2026-05-01-hitl-dataset-cli-design.md`
side by side with the new code. Confirm:

* `observation_ph_factory` defaults to `None`. ✓
* Explicit factory triggers `PIIGhostConfigWarning`. ✓
* HITL trace `input.text` stays raw regardless of factory (already
  ensured by the pre-existing override_detections logic). ✓
* CLI ships `serve`, `dataset extract`, `dataset metrics`. ✓
* JSONL records carry the `source` field. ✓
* Two PEP 723 scripts are gone. ✓

If any item disagrees with the spec, fix the implementation, re-run
Tasks 1-8 of this plan accordingly, and update this checklist.
