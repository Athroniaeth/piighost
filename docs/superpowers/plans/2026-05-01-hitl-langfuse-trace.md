# HITL Langfuse trace — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit one `piighost.hitl_correction` Langfuse trace per call to
`ThreadAnonymizationPipeline.override_detections`, carrying the model
detections (before) and the human-corrected detections (after) so model
quality can be evaluated offline.

**Architecture:** All changes are inside the `piighost` library, in
`src/piighost/pipeline/thread.py`. `override_detections` reads the
prior detection cache value, opens a flat root span via
`self._observation`, calls `span.update(input=..., output=...)` with
detections redacted via `_obs_tokens_for_detections` (existing helper
on `AnonymizationPipeline`), then proceeds with the existing cache
mutations. Observation is best-effort: a `try / except Exception`
around the span block prevents an unhealthy backend from breaking
`override_detections`.

**Tech Stack:** Python 3.12, aiocache, pytest-asyncio, pyrefly, ruff,
piighost's `AbstractObservationService` interface.

**Spec:** `docs/superpowers/specs/2026-05-01-hitl-langfuse-trace-design.md`

---

## File Structure

| File | Role | Action |
|---|---|---|
| `src/piighost/pipeline/thread.py` | Defines `ThreadAnonymizationPipeline.override_detections` | Modify |
| `tests/pipeline/test_anon_result_cache.py` | Existing tests for the anon-result cache and `override_detections` invalidation | Modify (add helpers, add three new tests, update one assertion) |

The work is small and tightly scoped. Splitting into a new test file
would fragment the `override_detections` test surface, so we keep
everything next to the existing
`test_override_detections_invalidates_anon_result`.

---

## Task 1: Emit a HITL trace from `override_detections`

This task adds the test helpers, writes the first failing test, makes
it pass by implementing the trace, and fixes the existing
`test_override_detections_invalidates_anon_result` whose assertion
becomes off-by-one because `override_detections` now opens a new span.

**Files:**
- Modify: `tests/pipeline/test_anon_result_cache.py`
- Modify: `src/piighost/pipeline/thread.py`

- [ ] **Step 1: Add `RecordingObservation` and `RecordingSpan` test helpers**

In `tests/pipeline/test_anon_result_cache.py`, also add a top-level
import for the model classes the new tests rely on (place the import
next to the existing piighost imports):

```python
from piighost.models import Detection, Span
```

Then add the helpers right after `CountingDetector` (around line 60).

```python
class RecordingSpan(NoOpSpan):
    """Span whose ``update()`` calls are captured for assertions."""

    def __init__(self) -> None:
        self.updates: list[dict[str, Any]] = []

    def update(
        self,
        *,
        input: Any = None,
        output: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {}
        if input is not None:
            kwargs["input"] = input
        if output is not None:
            kwargs["output"] = output
        if metadata is not None:
            kwargs["metadata"] = metadata
        self.updates.append(kwargs)


class RecordingObservation(AbstractObservationService):
    """Observation service that records spans and their update history."""

    def __init__(self) -> None:
        self.spans: list[tuple[dict[str, Any], RecordingSpan]] = []

    @contextmanager
    def start_as_current_span(self, **kwargs: Any):
        span = RecordingSpan()
        self.spans.append((kwargs, span))
        yield span
```

- [ ] **Step 2: Write failing test `test_override_detections_emits_hitl_span_with_redacted_diff`**

Append the test to the `TestAnonResultCacheThread` class in the same
file. The test runs an anonymize first to populate the detection cache
under thread `"t1"`, then calls `override_detections` with corrected
detections (label changed PERSON → ORG), and asserts the recorded
HITL span carries both lists in redacted form.

```python
async def test_override_detections_emits_hitl_span_with_redacted_diff(self) -> None:
    cache = SimpleMemoryCache()
    observation = RecordingObservation()
    detector = CountingDetector([("Patrick", "PERSON")])
    pipeline = ThreadAnonymizationPipeline(
        detector=detector,
        anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
        cache=cache,
        observation=observation,
    )

    # Populate the detection cache under thread t1 with the model output.
    await pipeline.anonymize("Bonjour Patrick", thread_id="t1")

    corrected = [
        Detection(
            text="Patrick",
            label="ORG",
            position=Span(start_pos=8, end_pos=15),
            confidence=1.0,
        )
    ]
    await pipeline.override_detections(
        "Bonjour Patrick", corrected, thread_id="t1"
    )

    hitl = [
        (kw, span)
        for kw, span in observation.spans
        if kw.get("name") == "piighost.hitl_correction"
    ]
    assert len(hitl) == 1
    kw, span = hitl[0]
    assert kw.get("tags") == ["hitl"]
    assert kw.get("session_id") == "t1"
    assert len(span.updates) == 1
    update = span.updates[0]
    assert "input" in update and "output" in update
    # Model said PERSON, human said ORG.
    assert update["input"]["detections"][0]["label"] == "PERSON"
    assert update["output"]["detections"][0]["label"] == "ORG"
    # Text is redacted (RedactPlaceholderFactory is the default obs factory).
    assert update["input"]["detections"][0]["text"] != "Patrick"
    assert update["output"]["detections"][0]["text"] != "Patrick"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/pipeline/test_anon_result_cache.py::TestAnonResultCacheThread::test_override_detections_emits_hitl_span_with_redacted_diff -v`

Expected: FAIL — `assert len(hitl) == 1` fails because no
`piighost.hitl_correction` span has been recorded yet (the current
`override_detections` only mutates the cache).

- [ ] **Step 4: Modify `override_detections` to emit the HITL trace**

Edit `src/piighost/pipeline/thread.py`. First, add a module logger at
the top, just below the existing imports (after line 25):

```python
import logging

logger = logging.getLogger(__name__)
```

Then replace the body of `override_detections` (currently lines 354-388)
with this version. The signature, docstring, and `RuntimeError` for
no-cache stay identical; only the body grows.

```python
async def override_detections(
    self,
    text: str,
    detections: list[Detection],
    thread_id: str = "default",
) -> None:
    """Override cached detection results for user corrections.

    Overwrites the detection cache entry for the given text so that
    subsequent calls to ``anonymize()`` use the corrected detections
    instead of re-running the detector. Also invalidates any cached
    anonymize result for the same text so the next ``anonymize``
    call actually re-runs the pipeline (and emits an observation
    trace) instead of returning the stale pre-correction result.

    Emits a flat ``piighost.hitl_correction`` root span (when an
    observation backend is configured) carrying the model detections
    as ``input`` and the human-corrected detections as ``output``,
    both redacted via the observation placeholder factory. The span
    is best-effort: a failing backend never breaks the cache update.

    Args:
        text: The original text whose detections should be overridden.
        detections: The corrected list of detections.
        thread_id: Thread identifier for cache isolation.

    Raises:
        RuntimeError: If no cache backend is configured.
    """
    if self._cache is None:
        raise RuntimeError("Cannot override detections without a cache backend")

    detect_key = self._thread_key(
        thread_id, f"{CACHE_KEY_DETECTION}:{hash_sha256(text)}"
    )
    anon_result_key = self._thread_key(
        thread_id, f"{CACHE_KEY_ANON_RESULT}:{hash_sha256(text)}"
    )

    # Read the prior model detections so the HITL trace can carry the
    # before/after pair. Empty list when nothing was cached before.
    prior = await self._cache.get(detect_key)
    before: list[Detection] = (
        self._deserialize_detections(prior) if prior is not None else []
    )

    try:
        with self._observation.start_as_current_span(
            name="piighost.hitl_correction",
            session_id=thread_id if thread_id != "default" else None,
            tags=["hitl"],
        ) as span:
            before_tokens = self._obs_tokens_for_detections(before)
            after_tokens = self._obs_tokens_for_detections(detections)
            span.update(
                input={
                    "detections": [
                        _detection_to_dict(d, token=before_tokens[d])
                        for d in before
                    ]
                },
                output={
                    "detections": [
                        _detection_to_dict(d, token=after_tokens[d])
                        for d in detections
                    ]
                },
            )
    except Exception:
        logger.warning(
            "HITL observation failed during override_detections; "
            "continuing with cache update.",
            exc_info=True,
        )

    value = self._serialize_detections(detections)
    await self._cache.set(detect_key, value, ttl=self._cache_ttl)
    await self._cache.delete(anon_result_key)
```

`_detection_to_dict` and `_obs_tokens_for_detections` are already
accessible: the first is imported at the top of `thread.py` from
`pipeline.base`, the second is inherited from `AnonymizationPipeline`.

- [ ] **Step 5: Run the new test to verify it passes**

Run: `uv run pytest tests/pipeline/test_anon_result_cache.py::TestAnonResultCacheThread::test_override_detections_emits_hitl_span_with_redacted_diff -v`

Expected: PASS.

- [ ] **Step 6: Update the existing `test_override_detections_invalidates_anon_result`**

Open `tests/pipeline/test_anon_result_cache.py`. Find the existing
test around line 183. Its final assertion `assert observation.span_count == 2`
no longer holds because `override_detections` now opens an extra HITL
span. Bump the expected count to `3` and tighten the comment:

```python
async def test_override_detections_invalidates_anon_result(self) -> None:
    pipeline, _, observation, _ = self._build()

    # First call populates both detect cache and anon-result cache.
    result1, _ = await pipeline.anonymize("Bonjour Patrick", thread_id="t1")
    assert "<<PERSON:1>>" in result1
    assert observation.span_count == 1

    # User corrects detections via HITL: declares no PII at all. This
    # opens its own observation span (piighost.hitl_correction) and
    # invalidates the anon-result cache.
    await pipeline.override_detections("Bonjour Patrick", [], thread_id="t1")
    assert observation.span_count == 2

    result2, ents = await pipeline.anonymize("Bonjour Patrick", thread_id="t1")
    # Third span: the anonymize re-ran because the anon-result cache
    # was invalidated by the override.
    assert observation.span_count == 3
```

- [ ] **Step 7: Run the full test class to confirm nothing else broke**

Run: `uv run pytest tests/pipeline/test_anon_result_cache.py -v`

Expected: every test in the file passes.

- [ ] **Step 8: Commit**

```bash
git add tests/pipeline/test_anon_result_cache.py src/piighost/pipeline/thread.py
git commit -m "$(cat <<'EOF'
feat(observation): emit HITL trace from override_detections

ThreadAnonymizationPipeline.override_detections now reads the prior
detection cache value, opens a piighost.hitl_correction root span
carrying redacted before/after detection lists, then proceeds with
the existing cache overwrite + anon-result invalidation. Observation
is best-effort: a try/except wrapping the span block keeps the user-
visible behaviour of override_detections unchanged when the
observation backend fails.
EOF
)"
```

---

## Task 2: Cover the empty-before edge case

Verify that `override_detections` still emits a clean HITL span when no
prior detection cache exists for the text (e.g. the chat client called
`PUT /v1/detect` without a preceding `POST /v1/detect`).

**Files:**
- Modify: `tests/pipeline/test_anon_result_cache.py`

- [ ] **Step 1: Add the edge-case test**

Append to the `TestAnonResultCacheThread` class:

```python
async def test_override_detections_emits_span_with_empty_before(self) -> None:
    cache = SimpleMemoryCache()
    observation = RecordingObservation()
    detector = CountingDetector([("Patrick", "PERSON")])
    pipeline = ThreadAnonymizationPipeline(
        detector=detector,
        anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
        cache=cache,
        observation=observation,
    )

    corrected = [
        Detection(
            text="Patrick",
            label="PERSON",
            position=Span(start_pos=8, end_pos=15),
            confidence=1.0,
        )
    ]
    # No anonymize / detect call before override → cache empty.
    await pipeline.override_detections(
        "Bonjour Patrick", corrected, thread_id="t1"
    )

    hitl = [
        (kw, span)
        for kw, span in observation.spans
        if kw.get("name") == "piighost.hitl_correction"
    ]
    assert len(hitl) == 1
    kw, span = hitl[0]
    update = span.updates[0]
    assert update["input"]["detections"] == []
    assert len(update["output"]["detections"]) == 1
    assert update["output"]["detections"][0]["label"] == "PERSON"
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/pipeline/test_anon_result_cache.py::TestAnonResultCacheThread::test_override_detections_emits_span_with_empty_before -v`

Expected: PASS — Task 1's implementation already handles the
`prior is None → before = []` branch.

If FAIL, fix `override_detections` so that the missing-cache case
serialises `[]` for `input.detections`, then re-run.

- [ ] **Step 3: Commit**

```bash
git add tests/pipeline/test_anon_result_cache.py
git commit -m "test(observation): cover empty-before HITL trace"
```

---

## Task 3: Cover observation backend failures

Pin down the best-effort behaviour: a misbehaving observation backend
must not raise out of `override_detections`, and the cache mutations
must still happen.

**Files:**
- Modify: `tests/pipeline/test_anon_result_cache.py`

- [ ] **Step 1: Add the failure-tolerance test**

Append to the `TestAnonResultCacheThread` class:

```python
async def test_override_detections_swallows_observation_errors(self) -> None:
    class RaisingObservation(AbstractObservationService):
        @contextmanager
        def start_as_current_span(self, **kwargs: Any):
            raise RuntimeError("backend exploded")
            yield NoOpSpan()  # pragma: no cover - unreachable

    cache = SimpleMemoryCache()
    pipeline = ThreadAnonymizationPipeline(
        detector=ExactMatchDetector([("Patrick", "PERSON")]),
        anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
        cache=cache,
        observation=RaisingObservation(),
    )

    corrected = [
        Detection(
            text="Patrick",
            label="ORG",
            position=Span(start_pos=8, end_pos=15),
            confidence=1.0,
        )
    ]

    # Must not raise even though the observation backend explodes.
    await pipeline.override_detections(
        "Bonjour Patrick", corrected, thread_id="t1"
    )

    # Cache was still overwritten with the corrected detections.
    detect_key = f"t1:{CACHE_KEY_DETECTION}:{hash_sha256('Bonjour Patrick')}"
    cached = await cache.get(detect_key)
    assert cached is not None
    # Decoded value should reflect the corrected ORG label.
    assert any(item["label"] == "ORG" for item in cached)
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/pipeline/test_anon_result_cache.py::TestAnonResultCacheThread::test_override_detections_swallows_observation_errors -v`

Expected: PASS — the `try / except Exception` from Task 1 already
wraps the span block.

If FAIL (the exception escapes), tighten the wrapping so the exception
is swallowed. Both the `with self._observation.start_as_current_span(...)`
opener and the `span.update(...)` inside the block must sit in the same
`try` so any failure during span lifecycle is logged, not raised.

- [ ] **Step 3: Commit**

```bash
git add tests/pipeline/test_anon_result_cache.py
git commit -m "test(observation): tolerate observation backend errors in override_detections"
```

---

## Task 4: Default `NoOpObservationService` keeps current behaviour

A regression check: when the user instantiates the pipeline without an
`observation` argument (the documented default), `override_detections`
must keep its existing user-visible contract — no exception, cache
mutation succeeds.

**Files:**
- Modify: `tests/pipeline/test_anon_result_cache.py`

- [ ] **Step 1: Add the default-config test**

Append to the `TestAnonResultCacheThread` class:

```python
async def test_override_detections_no_op_observation_keeps_contract(self) -> None:
    cache = SimpleMemoryCache()
    pipeline = ThreadAnonymizationPipeline(
        detector=ExactMatchDetector([("Patrick", "PERSON")]),
        anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
        cache=cache,
        # observation omitted → NoOpObservationService default
    )

    corrected = [
        Detection(
            text="Patrick",
            label="PERSON",
            position=Span(start_pos=8, end_pos=15),
            confidence=1.0,
        )
    ]
    await pipeline.override_detections(
        "Bonjour Patrick", corrected, thread_id="t1"
    )

    detect_key = f"t1:{CACHE_KEY_DETECTION}:{hash_sha256('Bonjour Patrick')}"
    cached = await cache.get(detect_key)
    assert cached is not None
    assert any(item["label"] == "PERSON" for item in cached)
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/pipeline/test_anon_result_cache.py::TestAnonResultCacheThread::test_override_detections_no_op_observation_keeps_contract -v`

Expected: PASS — `NoOpSpan.update` is already a no-op so the
implementation from Task 1 walks through without touching anything
visible.

- [ ] **Step 3: Commit**

```bash
git add tests/pipeline/test_anon_result_cache.py
git commit -m "test(observation): regression check for default NoOp observation override path"
```

---

## Task 5: Final verification

**Files:** none modified — verification only.

- [ ] **Step 1: Full test suite**

Run: `uv run pytest`

Expected: every test passes.

- [ ] **Step 2: Lint and type-check**

Run: `make lint`

Expected: ruff-format, ruff-check, and pyrefly all return clean.

- [ ] **Step 3: Eyeball the new behaviour against the spec**

Open `docs/superpowers/specs/2026-05-01-hitl-langfuse-trace-design.md`
side-by-side with the new `override_detections` body. Confirm:

- Trace `name == "piighost.hitl_correction"` ✓
- `tags == ["hitl"]` ✓
- `session_id` omitted when `thread_id == "default"` ✓
- `input.detections` and `output.detections` redacted ✓
- Cache mutation contract preserved (set + delete still happen
  even when observation fails) ✓

If any item disagrees with the spec, fix the implementation, re-run
Tasks 1-3 of this plan, and update this section's checklist.
