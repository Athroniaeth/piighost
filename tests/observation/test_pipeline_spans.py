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
