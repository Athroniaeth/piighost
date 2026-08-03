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
