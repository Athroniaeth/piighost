# HITL Langfuse trace — design spec

## Goal

Emit a single Langfuse trace for every Human-in-the-Loop detection
correction, so model-quality evaluation queries can compare model output
against human-corrected output over time.

Today `ThreadAnonymizationPipeline.override_detections` mutates the
detection cache silently. The next `anonymize` call produces a Langfuse
trace, but it is indistinguishable from a cold-start anonymize and does
not carry the model-versus-human signal needed for model evaluation.

## Use case

Model evaluation. The data point we want to capture is the pair
`(model_detections, human_detections)` for each correction event. The
human-corrected list is the ground truth; the model list is the
prediction. From these traces, an offline job (or a Langfuse export) can
compute precision / recall / label-confusion metrics per detector
version, per label, per thread.

## Non-goals

- Audit trail (use case B): not optimizing for tamper-evidence or
  per-user attribution. The trace is intended as evaluation data, not
  legal proof.
- Linking the HITL trace to the subsequent `anonymize` trace in the
  Langfuse UI. Correlation by `(thread_id, hash(text))` is sufficient
  for evaluation queries.
- Adding a Langfuse `score()` API call. Scores are tied to a
  `trace_id` that is not currently exposed by the
  `AbstractObservationService` interface, and adding that plumbing is
  not justified by the use case.
- Wiring a separate trace for `pipeline.detect_entities` (the
  `POST /v1/detect` path). The HITL trace already carries the
  `before` snapshot; a dedicated detect trace would duplicate that
  signal.

## Architecture

All changes land in the library `piighost`. No changes to
`piighost-api` or `piighost-chat` are required: both already configure
a `LangfuseObservationService` on the pipeline (via
`piighost_api.observation.load_observation_service`), so the new trace
will appear automatically once the library emits it.

### Surface modified

`ThreadAnonymizationPipeline.override_detections` in
`src/piighost/pipeline/thread.py`. Current implementation overwrites
the detection cache and invalidates the anon-result cache. The new
implementation reads the existing detection cache value first, opens a
`piighost.hitl_correction` root span via `self._observation`, populates
its `input` / `output`, and *then* writes / deletes the cache entries.

No new public method. No breaking change to the existing call signature.

### Trace shape

| Field | Value |
|---|---|
| `name` | `piighost.hitl_correction` |
| `as_type` | `span` (root) |
| `session_id` | `thread_id` (omitted when `"default"`, mirroring `anonymize`) |
| `tags` | `["hitl"]` |
| `input` | `{"detections": [<serialised model detections>]}` |
| `output` | `{"detections": [<serialised human detections>]}` |
| `metadata` | `{}` (reserved; nothing populated in v1) |

The trace is flat. No child spans.

### Detection serialisation

Each detection in `input` and `output` is rendered as:

```json
{
  "text": "<<PERSON:1>>",
  "label": "PERSON",
  "start_pos": 8,
  "end_pos": 15,
  "confidence": 0.91
}
```

`text` is the redacted form, produced by reusing the existing
`_obs_anonymizer` / `_obs_tokens_for_detections` helper on
`AnonymizationPipeline`. This is the same primitive used for child
spans inside `_anonymize_with_span`, so the redaction discipline is
consistent across all piighost traces.

`confidence` is preserved from `before` detections (model output) and
present-but-meaningless on `after` detections (human input has no model
score; it carries whatever the API client sent, typically `1.0`).

## Data flow

```
PUT /v1/detect
   → piighost-api  override_detect handler
   → pipeline.override_detections(text, after, thread_id)
       1. before := cache.get(detect:{thread_id}:{hash(text)})  # may be None
       2. with self._observation.start_as_current_span(
              name="piighost.hitl_correction",
              session_id=thread_id if thread_id != "default" else None,
              tags=["hitl"],
          ) as span:
              span.update(
                  input  = {"detections": serialise(before or [])},
                  output = {"detections": serialise(after)},
              )
       3. cache.set(detect:{...}, serialise(after))   # existing behaviour
       4. cache.delete(anon:result:{...})             # existing behaviour
```

The span is opened *before* the cache mutations. If a cache write
fails, the trace is still emitted (the user's correction was received
even if persistence failed). This matches the operational intent: the
trace is the canonical record of "a human corrected detections at this
moment".

## Edge cases

- **No cache backend configured**: existing
  `RuntimeError("Cannot override detections without a cache backend")`
  is raised before any observation work. Behaviour unchanged.
- **No prior detection cached for this text**: `before` is `None`,
  serialised as `[]`. The trace still fires; the signal is "the human
  added every detection from scratch".
- **`NoOpObservationService` configured**: `start_as_current_span`
  yields a `NoOpSpan` whose `update()` is a no-op. Zero overhead, zero
  trace emitted. Identical to the current default.
- **Observation backend raises** (network failure, SDK bug):
  observation is best-effort. The whole `with
  self._observation.start_as_current_span(...) as span: span.update(...)`
  block is wrapped in a `try / except Exception` that logs at WARNING
  level. The cache `set` and `delete` then run as before, so
  `override_detections` keeps its current user-visible contract even
  when the observation backend is broken.

## Testing

New file `tests/pipeline/test_hitl_observation.py` (or appended to
`test_anon_result_cache.py`). Three tests, plus a small helper.

### Helper: `RecordingObservation`

Modelled on `CountingObservation` (already in
`test_anon_result_cache.py`). Yields a `RecordingSpan` whose `update()`
captures its kwargs. The service records each `start_as_current_span`
call's kwargs and the resulting span's `update` history into a list of
`(start_kwargs, [update_kwargs, ...])` tuples so assertions can read
`name`, `tags`, `session_id`, `input`, `output` directly.

### Tests

1. **`test_override_detections_emits_hitl_span_with_redacted_diff`**
   — Pre-populate the detection cache by calling `pipeline.detect()` on
   `"Bonjour Patrick"`. Call
   `pipeline.override_detections("Bonjour Patrick", [<corrected>])`.
   Assert one span was opened with `name == "piighost.hitl_correction"`,
   `tags == ["hitl"]`, `session_id` matches the thread id, and that the
   `input.detections` and `output.detections` arrays carry the
   redacted-text form.

2. **`test_override_detections_emits_span_with_empty_before`**
   — Without any prior `detect()`, call `override_detections` directly.
   Assert one span was opened, `input.detections == []`,
   `output.detections` carries the human input.

3. **`test_override_detections_no_op_observation_emits_no_span`**
   — Configure pipeline with the default observation service (none).
   Call `override_detections`. Assert that the cache mutation still
   happens (existing behaviour preserved) and no exception is raised.

The existing test
`test_override_detections_invalidates_anon_result` keeps working
unchanged.

## Out of scope (future work)

- A `piighost.detect` root span for `detect_entities` calls coming
  through `POST /v1/detect`. Useful for monitoring detection volume /
  latency, but not needed for model evaluation.
- A Langfuse `score()` integration that ties HITL events to anonymize
  traces. Requires exposing `trace_id` on `AbstractSpan`; defer until a
  use case for it appears.
- An offline aggregation job that turns these traces into precision /
  recall metrics per label. Out of library scope; consumers can use
  Langfuse exports.
