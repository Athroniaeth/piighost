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

_TRACE_NAME_KEY = "langfuse.trace.name"
"""The root-span attribute Langfuse maps to the stored trace name.

Langfuse only fills a trace's stored name from this attribute; without it the
trace renders unnamed in list views, even though single-trace reads derive a
fallback from the root span.
"""


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

        A span opened with no ambient parent starts a new trace, so it also
        carries the Langfuse trace-name attribute; a child span never does, so a
        surrounding application trace keeps its own name. An exception raised
        inside the span is recorded on it and marks its status as error before
        propagating, which is OTel's default behavior.
        """
        is_root = not trace.get_current_span().get_span_context().is_valid
        with self._tracer.start_as_current_span(name) as span:
            if is_root:
                span.set_attribute(_TRACE_NAME_KEY, name)
            yield OtelSpan(span)
