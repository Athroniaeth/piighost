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

    def test_root_spans_carry_the_trace_name(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """A parentless span names its trace; a child span never does."""
        tracer = get_tracer()
        with tracer.span("piighost.root"):
            with tracer.span("piighost.child"):
                pass

        spans = {span.name: span for span in exporter.get_finished_spans()}
        root_attributes = spans["piighost.root"].attributes
        child_attributes = spans["piighost.child"].attributes
        assert root_attributes is not None
        assert child_attributes is not None
        assert root_attributes["langfuse.trace.name"] == "piighost.root"
        assert "langfuse.trace.name" not in child_attributes
