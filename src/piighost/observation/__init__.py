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
