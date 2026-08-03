# OpenTelemetry Observation Design

Design spec for the observation layer of the PIIGhost v2 rewrite. Internal
design document, French prose, English code identifiers.

## Context

The v2 pipelines (`AnonymizationPipeline`, `ThreadAnonymizationPipeline`) emit no
telemetry. The v1 lib had a custom observation port (`AbstractObservationService`
mirroring the Langfuse v3 vocabulary) with one handwritten adapter per backend
(langfuse, opik), a NoOp default injected into the pipeline, and a
timestamp-spacing workaround for Langfuse's millisecond precision.

Verified facts that reshape the approach: Langfuse ingests OpenTelemetry
natively (OTLP endpoint `/api/public/otel`), its Python SDK v3 is itself built
on OTel (spans from any OTel-instrumented library are captured automatically
once the app initializes the Langfuse client), and the rich rendering maps
documented span attributes (`langfuse.observation.input/output`,
`langfuse.session.id`, `langfuse.trace.name`). Opik, Phoenix, and the general
APM world ingest OTLP too.

## Goal

Instrument both pipelines with OpenTelemetry so each anonymization run produces
a structured trace (root span plus one child per executed stage), rendered
richly in Langfuse, with any other OTLP backend supported for free, and zero
overhead plus silent degradation when no tracer is configured.

## Key decisions

- **OpenTelemetry as the foundation, no per-backend adapters.** The pipeline
  emits spans through `opentelemetry-api`. Backends are the application's
  concern: initialize the Langfuse v3 SDK (OTel-based, automatic capture) or
  configure an OTLP exporter. One instrumentation, N backends; opik and others
  need documentation only. This replaces v1's custom port and adapters.
- **No `observation` parameter on the pipeline.** Injection is the global OTel
  `TracerProvider` configured by the application, per OTel's library
  instrumentation philosophy. The API is no-op by design when no provider is
  configured.
- **Silent degradation, a deliberate exception to the guarded-raise idiom.** A
  missing `observation` extra must not break anonymization: the seam falls back
  to a no-op stub instead of raising. Every other extra guards with
  `find_spec -> raise ImportError`, because a missing detector extra is a usage
  error; a missing tracer is not.
- **Clear payloads by default, redaction opt-in.** Trace payloads carry the
  message text and detection values in clear, so traces double as annotation
  datasets. An optional per-pipeline `observation_redactor` placeholder factory
  replaces those values with tokens. The observation backend becomes a PII
  custodian in the default mode; this is documented, not warned at runtime.
- **No timestamp-spacing hack.** OTel timestamps are nanosecond-precision and
  carried through OTLP, so the v1 pacing workaround is dropped.
- **Payloads are built even when no provider is configured.** When
  `opentelemetry-api` is importable (it often is, transitively), the seam is
  OTel-backed and every anonymize call serializes its payloads into attributes
  that a non-recording span then drops. Measured under a microsecond of overhead
  for typical texts, this is accepted; gating on `span.is_recording()` is the
  known optimization if profiling ever shows otherwise.

## Architecture

New package `src/piighost/observation/` (infra transverse, sibling of
`pipeline/`), three modules:

- `observation/base.py`: the seam surface and its no-op. A minimal span handle
  with `set_input(value)`, `set_output(value)`, `set_attribute(key, value)`, and
  a tracer whose `span(name)` is a context manager yielding a handle. Root and
  child nesting comes from the ambient OTel context, so the pipeline just opens
  spans as its stages run. The no-op tracer yields an inert handle.
- `observation/otel.py`: the OTel-backed implementation, wrapping
  `opentelemetry.trace.get_tracer("piighost")`. Payload values are
  JSON-serialized into the Langfuse-documented attribute keys
  (`langfuse.observation.input`, `langfuse.observation.output`); scalar
  attributes pass through. The module is guarded with the standard idiom,
  `if find_spec("opentelemetry") is None: raise ImportError(...piighost[
  observation])`, which keeps the module-walk regression test green.
- `observation/__init__.py`: resolves the seam once at import. When
  `opentelemetry` is importable it exposes the OTel tracer, otherwise the no-op
  stub, silently. This is where the documented exception to the raise pattern
  lives.

Both pipelines import the seam unconditionally and gain one optional constructor
parameter, `observation_redactor: AnyPlaceholderFactory | None = None`.

## Span tree

Per `anonymize` call:

- Root `piighost.anonymize`. Input: the message text. Output: the anonymized
  text. The thread pipeline also sets `langfuse.session.id` to the `thread_id`,
  so a thread's traces group into one Langfuse session. No `langfuse.trace.name`
  attribute is set: Langfuse derives the trace name from the root span's name.
- Children, in real execution order:
  - `piighost.detect`: output the detections (`Detection.to_dict()` list),
    attribute `count`, and on the thread pipeline `cache_hit` (true when the
    detections came from conversation memory and the detector did not run).
  - `piighost.overlap`, `piighost.expand`, `piighost.entity_resolve`: emitted
    only when the corresponding optional component is configured. No empty spans
    for disabled stages. These three are emitted by the base pipeline only: in
    the thread pipeline the overlap and expand stages run inside the cached
    detect step (on a cache miss) and entity resolution inside the thread-wide
    token assignment, so they are not separately spanned there.
  - `piighost.link`: output the entities (value, label, occurrence count).
  - `piighost.render`: output the anonymized text, attribute `tokens` (count).
  - `piighost.guard`: only when a guard is configured; output the verdict
    (flagged, residual labels). A raised `PIIRemainingError` marks the span as
    errored before propagating.
- `piighost.deanonymize` (thread pipeline): a simple root span, input the
  tokenized text, output the restored text.

## Payload redaction

With `observation_redactor` set, payloads carry factory tokens instead of clear
values: detection and entity payloads replace their `text` values, and the text
payloads (root input, render output) are redacted by replacing each of the
message's detection spans with its token. The root input is therefore attached
after the detect stage, once the detections are known. Redacted traces are
unusable as annotation datasets; this is documented in the parameter docstring,
with no runtime warning since setting the parameter is already the explicit
choice.

## Packaging

- Extra `observation = ["opentelemetry-api>=1.30"]` in
  `[project.optional-dependencies]`, mirrored in `[dependency-groups]`.
- The dev dependency group also gets `opentelemetry-sdk`, needed by the tests to
  install a `TracerProvider` with an `InMemorySpanExporter` and capture emitted
  spans. The lib itself never imports the SDK.

## Testing

The dev venv gets `opentelemetry-api` and `opentelemetry-sdk`, so the tests run
for real against an in-memory exporter:

- span tree: `anonymize` produces the root and children in order with the exact
  names; `cache_hit` is true on a thread cache hit; optional-stage spans are
  absent when their components are not configured; the guard span records the
  error when `PIIRemainingError` propagates;
- attributes: input/output serialized as JSON under the `langfuse.observation.*`
  keys; `langfuse.session.id` equals the thread id on the thread root;
- no-op fallback: the stub surface is exercised directly (a pipeline without any
  provider works unchanged and emits nothing);
- redaction: with `observation_redactor` set, no exported span attribute
  contains the clear value.

The `test_every_module_imports_cleanly` walk tolerates `observation/otel.py`'s
`piighost[observation]` ImportError like the other guarded modules. Only symbols
importable without the extra are added to the `PUBLIC_API` regression list.

## Out of scope

- Opik, Phoenix, or any backend-specific code (they consume OTLP; a later doc
  page covers configuration).
- `traceparent` context propagation in the HTTP client (the distributed-tracing
  follow-up).
- TOML config wiring for the redactor or the extra (config block is later).
- Metrics and logs; this is traces only.
- The v1 `update_trace` API and the timestamp-spacing workaround, both dropped.
