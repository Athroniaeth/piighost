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
