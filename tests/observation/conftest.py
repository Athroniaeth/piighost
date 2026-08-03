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
