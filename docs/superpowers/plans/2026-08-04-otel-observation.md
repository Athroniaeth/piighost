# OpenTelemetry Observation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Instrument both pipelines with OpenTelemetry so each anonymization run produces a structured trace (root span plus one child per executed stage) rendered richly in Langfuse, with silent no-op degradation when the extra is absent.

**Architecture:** A new `src/piighost/observation/` seam: a tiny tracer surface (`span(name)` context manager yielding a handle with `set_input`/`set_output`/`set_attribute`), resolved at `get_tracer()` to an OTel-backed implementation when `opentelemetry` is importable, else a no-op. The OTel implementation writes payloads as JSON under the Langfuse-documented attribute keys. Both pipelines open spans through the seam and gain one `observation_redactor` parameter for opt-in payload redaction.

**Tech Stack:** Python 3.11+, `opentelemetry-api` (extra `observation`), `opentelemetry-sdk` (dev only, for the in-memory exporter in tests), pytest (`asyncio_mode = "auto"`).

---

## Conventions for every task

- Run tests with `uv run --no-sync`. Before each pytest run clear bytecode: `find src tests -name __pycache__ -type d -exec rm -rf {} +`.
- `asyncio_mode = "auto"`: `async def test_...` needs NO decorator. flake8-annotations (ANN) is enforced on tests too.
- Python 3.11+ native typing, NO `from __future__ import annotations`. Docstrings plain prose plus bullet lists only, no markdown/RST. English only. Conventional Commits.
- Environment facts: `opentelemetry-api` is ALREADY importable in the dev venv (a transitive dependency of langchain), `opentelemetry.sdk` is NOT until Task 1 installs it. pyrefly resolves `opentelemetry` imports, so no pyrefly suppression is expected anywhere in this plan; if pyrefly reports an error, report it rather than suppressing.
- OTel background the implementer needs: `trace.get_tracer(...)` before any provider is configured returns a proxy that defers to the provider set later, so binding it in `__init__` is safe; `start_as_current_span` nests spans through the ambient context automatically and, on an exception, records it and sets the span status to error before propagating.

## File structure

- Modify `pyproject.toml` — extra + dev-group additions (Task 1).
- Create `src/piighost/observation/base.py` — seam protocols + no-op (Task 1).
- Create `src/piighost/observation/otel.py` — OTel-backed tracer (Task 1).
- Create `src/piighost/observation/__init__.py` — `get_tracer()` silent resolution (Task 1).
- Create `tests/observation/conftest.py` — in-memory exporter fixture (Task 1).
- Create `tests/observation/test_seam.py` (Task 1).
- Modify `src/piighost/pipeline/base.py` — span emission, `observation_redactor`, `_guard` returns the verdict (Task 2).
- Create `tests/observation/test_pipeline_spans.py` (Task 2).
- Modify `src/piighost/pipeline/thread.py` — span emission, session id, `cache_hit`, deanonymize root (Task 3).
- Create `tests/observation/test_thread_spans.py` (Task 3).
- Modify `tests/regression/test_imports.py` — new public symbols (Task 4).

---

### Task 1: Observation seam package and packaging

**Files:**
- Modify: `pyproject.toml`
- Create: `src/piighost/observation/base.py`
- Create: `src/piighost/observation/otel.py`
- Create: `src/piighost/observation/__init__.py`
- Create: `tests/observation/conftest.py`
- Test: `tests/observation/test_seam.py`

- [ ] **Step 1: Add the packaging entries and sync**

In `pyproject.toml`, in `[project.optional-dependencies]`, directly after the `llm = [...]` block, add:

```toml
observation = [
    "opentelemetry-api>=1.30",
]
```

In the `all = [...]` extra, add `observation` to the bracket list (keep the existing names, append `,observation` before the closing bracket).

In `[dependency-groups]`, directly after the `llm = [...]` block there, add the same mirror:

```toml
observation = [
    "opentelemetry-api>=1.30",
]
```

Still in `[dependency-groups]`, in the `dev = [...]` list, append two lines:

```toml
    "opentelemetry-api>=1.30",
    "opentelemetry-sdk>=1.30",
```

Then run: `uv sync`
Expected: installs `opentelemetry-sdk` (api already present). Verify with `uv run --no-sync python -c "import opentelemetry.sdk; print('ok')"` printing `ok`.

- [ ] **Step 2: Write the failing seam tests**

Create `tests/observation/conftest.py`:

```python
"""Shared OTel capture fixture for the observation tests.

The global tracer provider can only be set once per process, so it is installed
at collection time with an in-memory exporter, and each test clears the exporter
before running.
"""

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

_EXPORTER = InMemorySpanExporter()
_PROVIDER = TracerProvider()
_PROVIDER.add_span_processor(SimpleSpanProcessor(_EXPORTER))
trace.set_tracer_provider(_PROVIDER)


@pytest.fixture
def exporter() -> InMemorySpanExporter:
    """The in-memory span exporter, cleared before each test."""
    _EXPORTER.clear()
    return _EXPORTER
```

Create `tests/observation/test_seam.py`:

```python
"""Tests for the observation seam."""

import importlib.util
from typing import Any

from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from piighost.observation import AnyObservationTracer, NoOpTracer, get_tracer
from piighost.observation.otel import OtelTracer


class TestGetTracer:
    def test_returns_the_otel_tracer_when_available(self) -> None:
        """With opentelemetry importable, the seam is OTel-backed."""
        assert isinstance(get_tracer(), OtelTracer)

    def test_falls_back_to_noop_without_opentelemetry(self, monkeypatch: Any) -> None:
        """Without opentelemetry, the seam degrades silently to a no-op."""
        real_find_spec = importlib.util.find_spec

        def find_spec(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "opentelemetry":
                return None
            return real_find_spec(name, *args, **kwargs)

        monkeypatch.setattr(importlib.util, "find_spec", find_spec)
        assert isinstance(get_tracer(), NoOpTracer)


class TestNoOpTracer:
    def test_satisfies_the_tracer_protocol(self) -> None:
        """The no-op tracer honors the seam surface."""
        assert isinstance(NoOpTracer(), AnyObservationTracer)

    def test_span_yields_an_inert_handle(self) -> None:
        """The inert handle absorbs every call without effect."""
        with NoOpTracer().span("piighost.test") as span:
            span.set_input("in")
            span.set_output("out")
            span.set_attribute("count", 1)


class TestOtelTracer:
    def test_satisfies_the_tracer_protocol(self) -> None:
        """The OTel tracer honors the seam surface."""
        assert isinstance(OtelTracer(), AnyObservationTracer)

    def test_records_payloads_as_langfuse_attributes(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Payloads land as JSON under the Langfuse-mapped attribute keys."""
        with get_tracer().span("piighost.test") as span:
            span.set_input({"text": "hello"})
            span.set_output("world")
            span.set_attribute("count", 2)

        (recorded,) = exporter.get_finished_spans()
        assert recorded.name == "piighost.test"
        assert recorded.attributes is not None
        assert recorded.attributes["langfuse.observation.input"] == '{"text": "hello"}'
        assert recorded.attributes["langfuse.observation.output"] == "world"
        assert recorded.attributes["count"] == 2
```

- [ ] **Step 3: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/observation/test_seam.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'piighost.observation'`.

- [ ] **Step 4: Write the seam**

Create `src/piighost/observation/base.py`:

```python
"""Observation seam surface: the tracing contract the pipelines emit through.

A tracer opens named spans as context managers; nesting comes from the ambient
tracing context, so a span opened inside another becomes its child. The handle
records an input payload, an output payload, and scalar attributes. The no-op
implementations record nothing and cost nothing, so a pipeline can always emit
without checking whether tracing is configured.
"""

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AnyObservationSpan(Protocol):
    """A handle to one observation being recorded."""

    def set_input(self, value: Any) -> None:
        """Record the observation's input payload."""
        ...

    def set_output(self, value: Any) -> None:
        """Record the observation's output payload."""
        ...

    def set_attribute(self, key: str, value: str | int | float | bool) -> None:
        """Record one scalar attribute on the observation."""
        ...


@runtime_checkable
class AnyObservationTracer(Protocol):
    """A factory of observation spans, nested by the ambient context."""

    def span(self, name: str) -> AbstractContextManager[AnyObservationSpan]:
        """Open a span with the given name and yield its handle."""
        ...


class NoOpSpan:
    """A span handle that records nothing."""

    def set_input(self, value: Any) -> None:
        """Discard the input payload."""
        return None

    def set_output(self, value: Any) -> None:
        """Discard the output payload."""
        return None

    def set_attribute(self, key: str, value: str | int | float | bool) -> None:
        """Discard the attribute."""
        return None


class NoOpTracer:
    """A tracer that records nothing, used when opentelemetry is absent."""

    @contextmanager
    def span(self, name: str) -> Iterator[NoOpSpan]:
        """Yield an inert span handle."""
        yield NoOpSpan()
```

Create `src/piighost/observation/otel.py`:

```python
"""OpenTelemetry-backed observation tracer (optional: observation).

Spans flow to whatever TracerProvider the application configured, per OTel's
library-instrumentation model: with no provider the API is a no-op. Payloads are
serialized as JSON under the attribute keys Langfuse maps to observation input
and output, so traces render richly there while any other OTLP backend still
shows them as plain attributes.
"""

import importlib.util
import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

if importlib.util.find_spec("opentelemetry") is None:
    raise ImportError(
        "The OTel observation tracer requires the opentelemetry-api package. "
        "Install it with: pip install piighost[observation]"
    )

from opentelemetry import trace  # noqa: E402

_INPUT_KEY = "langfuse.observation.input"
"""The span attribute Langfuse maps to the observation's input."""

_OUTPUT_KEY = "langfuse.observation.output"
"""The span attribute Langfuse maps to the observation's output."""


def _as_attribute(value: Any) -> str:
    """Serialize a payload to the JSON string Langfuse expects, strings as-is."""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


class OtelSpan:
    """A span handle writing payloads as Langfuse-mapped OTel attributes."""

    def __init__(self, span: trace.Span) -> None:
        """Wrap one OTel span."""
        self._span = span

    def set_input(self, value: Any) -> None:
        """Record the input payload under the Langfuse input attribute."""
        self._span.set_attribute(_INPUT_KEY, _as_attribute(value))

    def set_output(self, value: Any) -> None:
        """Record the output payload under the Langfuse output attribute."""
        self._span.set_attribute(_OUTPUT_KEY, _as_attribute(value))

    def set_attribute(self, key: str, value: str | int | float | bool) -> None:
        """Record one scalar attribute as-is."""
        self._span.set_attribute(key, value)


class OtelTracer:
    """A tracer emitting piighost spans through the global OTel provider."""

    def __init__(self) -> None:
        """Bind the piighost instrumentation tracer."""
        self._tracer = trace.get_tracer("piighost")

    @contextmanager
    def span(self, name: str) -> Iterator[OtelSpan]:
        """Open a span in the ambient context and yield its handle.

        An exception raised inside the span is recorded on it and marks its
        status as error before propagating, which is OTel's default behavior.
        """
        with self._tracer.start_as_current_span(name) as span:
            yield OtelSpan(span)
```

Create `src/piighost/observation/__init__.py`:

```python
"""Observation: OpenTelemetry-based tracing of the pipelines.

The pipelines emit spans through the seam returned by get_tracer. Backends are
the application's concern: initialize the Langfuse v3 SDK (built on OTel, it
captures these spans automatically) or configure any OTLP exporter. Unlike the
other optional dependencies, a missing extra degrades silently to a no-op
instead of raising, because tracing must never be required for anonymization to
work.
"""

import importlib.util

from piighost.observation.base import (
    AnyObservationSpan,
    AnyObservationTracer,
    NoOpSpan,
    NoOpTracer,
)

__all__ = [
    "AnyObservationSpan",
    "AnyObservationTracer",
    "NoOpSpan",
    "NoOpTracer",
    "get_tracer",
]


def get_tracer() -> AnyObservationTracer:
    """Return the OTel-backed tracer, or a no-op one without the extra."""
    if importlib.util.find_spec("opentelemetry") is None:
        return NoOpTracer()

    from piighost.observation.otel import OtelTracer

    return OtelTracer()
```

- [ ] **Step 5: Run it to verify it passes**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/observation/test_seam.py tests/regression/test_imports.py -q`
Expected: PASS (6 seam tests plus the regression module; the walk imports `piighost.observation.otel` cleanly since opentelemetry is installed).

- [ ] **Step 6: Lint and types, then commit**

Run: `uv run --no-sync ruff format src/piighost/observation tests/observation && uv run --no-sync ruff check src/piighost/observation tests/observation && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean, pyrefly 0 errors.

```bash
git add pyproject.toml uv.lock src/piighost/observation tests/observation/conftest.py tests/observation/test_seam.py
git commit -m "feat(observation): add the OpenTelemetry observation seam"
```

---

### Task 2: Base pipeline span emission

**Files:**
- Modify: `src/piighost/pipeline/base.py`
- Test: `tests/observation/test_pipeline_spans.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/observation/test_pipeline_spans.py`:

```python
"""Span-tree tests for the base anonymization pipeline."""

from typing import Any

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.guard import DetectorGuardRail
from piighost.components.linker import ExactEntityLinker
from piighost.components.overlap_resolver import ConfidenceOverlapResolver
from piighost.components.placeholder import (
    LabelCounterPlaceholderFactory,
    RedactPlaceholderFactory,
)
from piighost.exceptions import PIIRemainingError
from piighost.pipeline import AnonymizationPipeline


def _pipeline(**kwargs: Any) -> AnonymizationPipeline:
    """Build a base pipeline knowing one name, extra stages via kwargs."""
    return AnonymizationPipeline(
        ExactMatchDetector({"Emma": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(LabelCounterPlaceholderFactory()),
        **kwargs,
    )


class TestSpanTree:
    async def test_emits_root_and_stage_spans_in_finish_order(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """One run emits detect, link, render, then the root, and nothing else."""
        await _pipeline().anonymize("Hi Emma!")
        names = [span.name for span in exporter.get_finished_spans()]
        assert names == [
            "piighost.detect",
            "piighost.link",
            "piighost.render",
            "piighost.anonymize",
        ]

    async def test_children_nest_under_the_root(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Every stage span is a direct child of the root span."""
        await _pipeline().anonymize("Hi Emma!")
        spans = {span.name: span for span in exporter.get_finished_spans()}
        root = spans["piighost.anonymize"]
        assert root.parent is None
        for name in ("piighost.detect", "piighost.link", "piighost.render"):
            parent = spans[name].parent
            assert parent is not None
            assert parent.span_id == root.context.span_id

    async def test_optional_stage_spans_appear_when_configured(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Configured optional stages get spans; disabled ones never do."""
        pipeline = _pipeline(
            overlap_resolver=ConfidenceOverlapResolver(),
            guard=DetectorGuardRail(ExactMatchDetector({})),
        )
        await pipeline.anonymize("Hi Emma!")
        names = [span.name for span in exporter.get_finished_spans()]
        assert "piighost.overlap" in names
        assert "piighost.guard" in names
        assert "piighost.expand" not in names
        assert "piighost.entity_resolve" not in names

    async def test_root_records_input_and_output(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """The root span carries the clear input and the anonymized output."""
        await _pipeline().anonymize("Hi Emma!")
        spans = {span.name: span for span in exporter.get_finished_spans()}
        attributes = spans["piighost.anonymize"].attributes
        assert attributes is not None
        assert attributes["langfuse.observation.input"] == "Hi Emma!"
        assert attributes["langfuse.observation.output"] == "Hi <<PERSON:1>>!"

    async def test_detect_span_carries_count_and_detections(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """The detect span reports the count and the serialized detections."""
        await _pipeline().anonymize("Hi Emma!")
        spans = {span.name: span for span in exporter.get_finished_spans()}
        attributes = spans["piighost.detect"].attributes
        assert attributes is not None
        assert attributes["count"] == 1
        assert '"Emma"' in str(attributes["langfuse.observation.output"])

    async def test_flagged_guard_marks_the_span_errored(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """A PIIRemainingError records an error status on the guard span."""
        guard = DetectorGuardRail(ExactMatchDetector({"leak@x.com": "EMAIL"}))
        pipeline = _pipeline(guard=guard)
        with pytest.raises(PIIRemainingError):
            await pipeline.anonymize("Emma wrote leak@x.com")
        spans = {span.name: span for span in exporter.get_finished_spans()}
        assert spans["piighost.guard"].status.status_code.name == "ERROR"


class TestRedaction:
    async def test_redactor_removes_clear_values_from_payloads(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """With a redactor, no exported attribute holds the clear value."""
        pipeline = _pipeline(observation_redactor=RedactPlaceholderFactory())
        await pipeline.anonymize("Hi Emma!")
        for span in exporter.get_finished_spans():
            for value in (span.attributes or {}).values():
                assert "Emma" not in str(value)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/observation/test_pipeline_spans.py -q`
Expected: FAIL (no spans are emitted yet, and `observation_redactor` is not an accepted parameter).

- [ ] **Step 3: Instrument the base pipeline**

In `src/piighost/pipeline/base.py`:

Add to the imports (`nullcontext` joins the existing `dataclasses` import area; keep import groups sorted):

```python
from contextlib import AbstractContextManager, nullcontext
from typing import Any, Generic, Protocol, runtime_checkable

from piighost.components.placeholder.base import AnyPlaceholderFactory
from piighost.observation import AnyObservationSpan, NoOpSpan, get_tracer
```

Extend `__init__` (new last parameter, new attribute lines, docstring attribute added):

```python
    def __init__(
        self,
        detector: AnyDetector,
        linker: AnyEntityLinker,
        anonymizer: AnyAnonymizer[PreservationT],
        overlap_resolver: AnyOverlapResolver | None = None,
        expander: AnyDetectionExpander | None = None,
        entity_resolver: AnyEntityResolver | None = None,
        guard: AnyGuardRail | None = None,
        observation_redactor: AnyPlaceholderFactory | None = None,
    ) -> None:
        """Store the stage components, the optional ones defaulting to disabled.

        observation_redactor controls the observation payloads: None, the
        default, traces the clear text and detection values, so traces double as
        annotation datasets; a placeholder factory replaces those values with its
        tokens, making traces safe for a PII-untrusted backend but unusable as
        datasets.
        """
        self.detector = detector
        self.linker = linker
        self.anonymizer = anonymizer
        self.overlap_resolver = overlap_resolver
        self.expander = expander
        self.entity_resolver = entity_resolver
        self.guard = guard
        self.observation_redactor = observation_redactor
        self._tracer = get_tracer()
```

Add the emission helpers to `BaseAnonymizationPipeline` (after `_resolve_entities`):

```python
    def _stage_span(
        self, name: str, component: object | None
    ) -> AbstractContextManager[AnyObservationSpan]:
        """Open a stage span when the component is configured, else a no-op."""
        if component is None:
            return nullcontext(NoOpSpan())
        return self._tracer.span(name)

    def _payload_detections(self, detections: list[Detection]) -> list[dict[str, Any]]:
        """Serialize detections for a span payload, tokened when redacting."""
        if self.observation_redactor is None:
            return [detection.to_dict() for detection in detections]
        tokens = self._redaction_tokens(detections)
        return [
            {**detection.to_dict(), "text": tokens[detection]}
            for detection in detections
        ]

    def _payload_entities(self, entities: list[Entity]) -> list[dict[str, Any]]:
        """Serialize entities for a span payload, tokened when redacting."""
        if self.observation_redactor is None:
            values = {entity: entity.text for entity in entities}
        else:
            tokens = self.observation_redactor.create(entities)
            values = {entity: str(tokens[entity]) for entity in entities}
        return [
            {
                "text": values[entity],
                "label": entity.label,
                "occurrences": len(entity.detections),
            }
            for entity in entities
        ]

    def _payload_text(self, text: str, detections: list[Detection]) -> str:
        """Return a text payload, its detection spans tokened when redacting."""
        if self.observation_redactor is None:
            return text
        tokens = self._redaction_tokens(detections)
        redacted = text
        ordered = sorted(detections, key=lambda detection: detection.span, reverse=True)
        for detection in ordered:
            span = detection.span
            redacted = redacted[: span.start] + tokens[detection] + redacted[span.end :]
        return redacted

    def _redaction_tokens(self, detections: list[Detection]) -> dict[Detection, str]:
        """Token every detection with the redactor, grouped so values share one."""
        redactor = self.observation_redactor
        if redactor is None:
            return {}
        entities = self.linker.link(detections)
        tokens = redactor.create(entities)
        return {
            detection: str(tokens[entity])
            for entity in entities
            for detection in entity.detections
        }
```

Change `_guard` to return the verdict (same logic, the early return now reports an unflagged verdict):

```python
    async def _guard(
        self, text: str, expected: frozenset[str] = frozenset()
    ) -> GuardVerdict | None:
        """Check the guard and raise on unexpected PII, returning the verdict.

        Values in expected are ones the pipeline chose to leave in clear, such as
        an entity the assistant introduced. A detector-based guard would re-find
        them, so they are dropped from the verdict before deciding. A score-based
        guard localizes nothing, so it cannot be filtered this way. Returns None
        when no guard is configured, else the verdict that passed.
        """
        if self.guard is None:
            return None

        verdict = await self.guard.check(text)

        if verdict.detections:
            residual = tuple(
                detection
                for detection in verdict.detections
                if detection.text.casefold() not in expected
            )
            if not residual:
                return replace(verdict, flagged=False, detections=())
            verdict = replace(verdict, detections=residual)

        if verdict.flagged:
            raise _pii_remaining(verdict)
        return verdict
```

Rewrite `AnonymizationPipeline.anonymize` with the span emission:

```python
    async def anonymize(self, text: str) -> Anonymization[PreservationT]:
        """Return the anonymized text and token mapping for the given text.

        Raises:
            PIIRemainingError: If a guard flags PII left in the output.
        """
        with self._tracer.span("piighost.anonymize") as root:
            with self._tracer.span("piighost.detect") as span:
                detections = await self.detector.detect(text)
                span.set_attribute("count", len(detections))
                span.set_output(self._payload_detections(detections))
            root.set_input(self._payload_text(text, detections))

            with self._stage_span("piighost.overlap", self.overlap_resolver):
                detections = self._resolve_overlaps(detections)
            with self._stage_span("piighost.expand", self.expander):
                detections = self._expand(text, detections)

            with self._tracer.span("piighost.link") as span:
                entities = self._link(detections)
                span.set_output(self._payload_entities(entities))

            with self._stage_span("piighost.entity_resolve", self.entity_resolver):
                entities = self._resolve_entities(entities)

            with self._tracer.span("piighost.render") as span:
                result = self.anonymizer.anonymize(text, entities)
                span.set_attribute("tokens", len(result.tokens))
                span.set_output(result.text)

            with self._stage_span("piighost.guard", self.guard) as span:
                verdict = await self._guard(result.text)
                if verdict is not None:
                    labels = sorted({d.label for d in verdict.detections})
                    span.set_output({"flagged": verdict.flagged, "labels": labels})

            root.set_output(result.text)
            return result
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/observation/ -q`
Expected: PASS (seam + pipeline span tests).

- [ ] **Step 5: Run the full suite, lint, and types**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest -q`
Expected: PASS, no regressions (existing pipeline tests are unaffected: spans go to the provider installed by the observation conftest or nowhere).

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean, pyrefly 0 errors.

- [ ] **Step 6: Commit**

```bash
git add src/piighost/pipeline/base.py tests/observation/test_pipeline_spans.py
git commit -m "feat(pipeline): emit OpenTelemetry spans from the base pipeline"
```

---

### Task 3: Thread pipeline span emission

**Files:**
- Modify: `src/piighost/pipeline/thread.py`
- Test: `tests/observation/test_thread_spans.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/observation/test_thread_spans.py`:

```python
"""Span-tree tests for the thread anonymization pipeline."""

from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.pipeline import ThreadAnonymizationPipeline


def _pipeline() -> ThreadAnonymizationPipeline:
    """Build a thread pipeline knowing one name over an in-memory backend."""
    return ThreadAnonymizationPipeline(
        ExactMatchDetector({"Emma": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(LabelCounterPlaceholderFactory()),
        InMemoryConversationMemory(),
    )


class TestThreadSpans:
    async def test_root_carries_the_session_id(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """The root span maps the thread id to the Langfuse session."""
        await _pipeline().anonymize("Hi Emma", "t42")
        spans = {span.name: span for span in exporter.get_finished_spans()}
        attributes = spans["piighost.anonymize"].attributes
        assert attributes is not None
        assert attributes["langfuse.session.id"] == "t42"

    async def test_detect_span_reports_a_cache_miss_then_a_hit(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """The first pass misses the cache, resending the message hits it."""
        pipeline = _pipeline()
        await pipeline.anonymize("Hi Emma", "t1")
        spans = {span.name: span for span in exporter.get_finished_spans()}
        attributes = spans["piighost.detect"].attributes
        assert attributes is not None
        assert attributes["cache_hit"] is False

        exporter.clear()
        await pipeline.anonymize("Hi Emma", "t1")
        spans = {span.name: span for span in exporter.get_finished_spans()}
        attributes = spans["piighost.detect"].attributes
        assert attributes is not None
        assert attributes["cache_hit"] is True

    async def test_stage_spans_nest_under_the_thread_root(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """The thread flow emits detect, link, and render under the root."""
        await _pipeline().anonymize("Hi Emma", "t1")
        spans = {span.name: span for span in exporter.get_finished_spans()}
        root = spans["piighost.anonymize"]
        for name in ("piighost.detect", "piighost.link", "piighost.render"):
            parent = spans[name].parent
            assert parent is not None
            assert parent.span_id == root.context.span_id

    async def test_deanonymize_emits_its_own_root(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Deanonymization traces a simple root with input and output."""
        pipeline = _pipeline()
        await pipeline.anonymize("Hi Emma", "t1")
        exporter.clear()

        restored = await pipeline.deanonymize("<<PERSON:1>>", "t1")
        assert restored == "Emma"
        spans = {span.name: span for span in exporter.get_finished_spans()}
        attributes = spans["piighost.deanonymize"].attributes
        assert attributes is not None
        assert attributes["langfuse.observation.input"] == "<<PERSON:1>>"
        assert attributes["langfuse.observation.output"] == "Emma"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/observation/test_thread_spans.py -q`
Expected: FAIL (the thread pipeline emits no thread-specific spans yet).

- [ ] **Step 3: Instrument the thread pipeline**

In `src/piighost/pipeline/thread.py`:

Add `observation_redactor` to the constructor (new last parameter, forwarded to super):

```python
    def __init__(
        self,
        detector: AnyDetector,
        linker: AnyEntityLinker,
        anonymizer: AnyAnonymizer[PreservationT],
        memory: AnyConversationMemory,
        overlap_resolver: AnyOverlapResolver | None = None,
        expander: AnyDetectionExpander | None = None,
        entity_resolver: AnyEntityResolver | None = None,
        guard: AnyGuardRail | None = None,
        observation_redactor: "AnyPlaceholderFactory | None" = None,
    ) -> None:
        """Store the stage components and the per-thread conversation memory."""
        super().__init__(
            detector,
            linker,
            anonymizer,
            overlap_resolver,
            expander,
            entity_resolver,
            guard,
            observation_redactor,
        )
        self.memory = memory
```

with the matching import added at the top: `from piighost.components.placeholder.base import AnyPlaceholderFactory` (unquote the annotation if no cycle arises; the quoted form is only a fallback).

Change `_detect` to report cache hits (same logic, tuple return):

```python
    async def _detect(
        self,
        text: str,
        thread_id: str,
        role: MessageRole = MessageRole.USER,
    ) -> tuple[list[Detection], bool]:
        """Return a message's detections and whether they came from the cache."""
        cached = await self.memory.get_detections(thread_id, text)

        if cached is not None:
            return cached, True

        detections = await self.detector.detect(text)
        detections = self._resolve_overlaps(detections)
        detections = self._expand(text, detections)
        await self.memory.remember(
            message=text,
            thread_id=thread_id,
            detections=detections,
            role=role,
        )
        return detections, False
```

Rewrite `anonymize` with the span emission (same logic wrapped in spans; docstring unchanged from the current one):

```python
    async def anonymize(
        self,
        text: str,
        thread_id: str,
        role: MessageRole = MessageRole.USER,
    ) -> Anonymization[PreservationT]:
        """Anonymize a message with tokens consistent across its thread.

        The thread_id is required: there is no shared default, so two callers
        cannot fall into one thread and leak each other's PII. The role dates the
        values the message introduces: a value first introduced by the assistant
        is left in clear, since it is not user PII.

        Raises:
            PIIRemainingError: If a guard flags PII left in the output.
        """
        with self._tracer.span("piighost.anonymize") as root:
            root.set_attribute("langfuse.session.id", thread_id)

            with self._tracer.span("piighost.detect") as span:
                detections, cache_hit = await self._detect(text, thread_id, role)
                span.set_attribute("cache_hit", cache_hit)
                span.set_attribute("count", len(detections))
                span.set_output(self._payload_detections(detections))
            root.set_input(self._payload_text(text, detections))

            thread_tokens = await self._thread_tokens(thread_id)
            token_of = {
                detection: token
                for entity, token in thread_tokens.items()
                for detection in entity.detections
            }

            with self._tracer.span("piighost.link") as span:
                message_entities = self.linker.link(detections)
                span.set_output(self._payload_entities(message_entities))

            message_tokens = {
                entity: token_of[entity.detections[0]]
                for entity in message_entities
                if entity.detections[0] in token_of
            }
            preserved = frozenset(
                entity.text.casefold()
                for entity in message_entities
                if entity.detections[0] not in token_of
            )
            anonymizable = list(message_tokens)

            with self._tracer.span("piighost.render") as span:
                rendered = self.anonymizer.render(text, anonymizable, message_tokens)
                span.set_attribute("tokens", len(message_tokens))
                span.set_output(rendered)

            with self._stage_span("piighost.guard", self.guard) as span:
                verdict = await self._guard(rendered, preserved)
                if verdict is not None:
                    labels = sorted({d.label for d in verdict.detections})
                    span.set_output({"flagged": verdict.flagged, "labels": labels})

            root.set_output(rendered)
            return Anonymization(text=rendered, tokens=message_tokens)
```

Rewrite `deanonymize` with its root span:

```python
    async def deanonymize(self, text: str, thread_id: str) -> str:
        """Return the text with every token from the thread replaced by its value.

        The thread's tokens are rebuilt from its memory, so any text carrying
        them is restored, including a model reply the pipeline never anonymized.
        """
        with self._tracer.span("piighost.deanonymize") as root:
            root.set_input(text)
            thread_tokens = await self._thread_tokens(thread_id)
            restored = self.anonymizer.deanonymize(text, thread_tokens)
            if self.observation_redactor is None:
                root.set_output(restored)
            return restored
```

The restored text is clear PII by definition, so in redaction mode the output payload is simply omitted.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/observation/ tests/pipeline/ -q`
Expected: PASS (observation tests plus the existing pipeline and HITL suites, whose behavior is unchanged).

- [ ] **Step 5: Run the full suite, lint, and types**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest -q`
Expected: PASS.

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean, pyrefly 0 errors.

- [ ] **Step 6: Commit**

```bash
git add src/piighost/pipeline/thread.py tests/observation/test_thread_spans.py
git commit -m "feat(pipeline): emit OpenTelemetry spans from the thread pipeline"
```

---

### Task 4: Public-API regression and full verification

**Files:**
- Modify: `tests/regression/test_imports.py`

- [ ] **Step 1: Add the observation symbols to the regression guard**

In `tests/regression/test_imports.py`, in the `PUBLIC_API` list, after the last `("piighost.conversation_memory", ...)` line, add:

```python
    ("piighost.observation", "AnyObservationSpan"),
    ("piighost.observation", "AnyObservationTracer"),
    ("piighost.observation", "NoOpSpan"),
    ("piighost.observation", "NoOpTracer"),
    ("piighost.observation", "get_tracer"),
```

These are all importable without the extra (`observation/base.py` has no optional import; `get_tracer` only probes). Do NOT add `OtelTracer`/`OtelSpan` (their module needs the extra; the walk covers them).

- [ ] **Step 2: Run the regression guard, the full suite, and the checks**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/regression/test_imports.py -q`
Expected: PASS with the five new cases.

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest -q`
Expected: PASS.

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean, pyrefly 0 errors.

- [ ] **Step 3: Commit**

```bash
git add tests/regression/test_imports.py
git commit -m "test(observation): guard the observation public symbols"
```

---

## Notes for the implementer

- The pipelines must keep working with NO provider configured and with the extra absent: never make emission conditional in pipeline code beyond `_stage_span`; the seam and the OTel API absorb everything.
- `_guard`'s return-type change (None -> `GuardVerdict | None`) is deliberate and non-breaking (no existing caller uses the return value); do not "simplify" it back.
- The observation conftest sets the GLOBAL tracer provider at collection time; that is intentional (OTel allows one provider per process). Do not try to build per-test providers.
- Span finish order in assertions is children-first (a child span ends before its parent), hence `detect, link, render, anonymize`.
- The redaction helpers group detections through the pipeline's own linker so case variants share one token; the redactor factory must be deterministic, which every shipped factory is.
- No pyrefly suppression is expected anywhere; opentelemetry resolves. If pyrefly flags something, report it.
