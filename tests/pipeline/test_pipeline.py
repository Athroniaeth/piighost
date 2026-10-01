"""Tests for the AnonymizationPipeline, wired from real components."""

import pytest

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import (
    CompositeDetector,
    ExactMatchDetector,
    RegexDetector,
)
from piighost.components.entity_resolver import MergeEntityResolver
from piighost.components.expander import WordBoundaryExpander
from piighost.components.guard import DetectorGuardRail
from piighost.components.linker import ExactEntityLinker
from piighost.components.overlap_resolver import ConfidenceOverlapResolver
from piighost.components.placeholder import (
    LabelCounterPlaceholderFactory,
    RedactPlaceholderFactory,
)
from piighost.exceptions import PIIRemainingError
from piighost.models import Detection, Span
from piighost.pipeline import AnonymizationPipeline, AnyPipeline


def _pipeline() -> AnonymizationPipeline:
    """Build a minimal working pipeline for conformance checks."""
    return AnonymizationPipeline(
        ExactMatchDetector({"Emma": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(RedactPlaceholderFactory()),
    )


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """AnonymizationPipeline is an AnyPipeline."""
        assert isinstance(_pipeline(), AnyPipeline)


class TestAnonymize:
    async def test_replaces_detected_pii(self) -> None:
        """Detected values become their tokens, the rest of the text stays."""
        pipeline = AnonymizationPipeline(
            ExactMatchDetector({"Emma": "PERSON", "Liam": "PERSON"}),
            ExactEntityLinker(),
            Anonymizer(LabelCounterPlaceholderFactory()),
        )
        result = await pipeline.anonymize("Emma met Liam")
        assert result.text == "<<PERSON:1>> met <<PERSON:2>>"

    async def test_overlapping_detections_are_resolved_by_default(self) -> None:
        """Overlapping detections are reconciled without an explicit resolver.

        The overlap resolver is on by default, so a composite whose children
        overlap yields a single token and never leaks a clear fragment of the
        losing detection.
        """
        person = ExactMatchDetector({"Patrick Dupont": "PERSON"})
        org = ExactMatchDetector({"Dupo": "ORG"})
        detector = CompositeDetector([person, org])
        pipeline = AnonymizationPipeline(
            detector,
            ExactEntityLinker(),
            Anonymizer(LabelCounterPlaceholderFactory()),
        )
        result = await pipeline.anonymize("Call Patrick Dupont today.")
        assert result.text == "Call <<PERSON:1>> today."

    async def test_repeats_group_into_one_token(self) -> None:
        """A value seen twice links to one entity and one token."""
        pipeline = AnonymizationPipeline(
            ExactMatchDetector({"Emma": "PERSON"}),
            ExactEntityLinker(),
            Anonymizer(LabelCounterPlaceholderFactory()),
        )
        result = await pipeline.anonymize("Emma and Emma")
        assert result.text == "<<PERSON:1>> and <<PERSON:1>>"

    async def test_defaults_to_link_and_counter_tokens(self) -> None:
        """Omitting linker and anonymizer links exactly and tokens by label counter."""
        pipeline = AnonymizationPipeline(
            ExactMatchDetector({"John Doe": "PERSON", "Paris": "LOCATION"}),
        )
        result = await pipeline.anonymize("John Doe lives in Paris.")
        assert result.text == "<<PERSON:1>> lives in <<LOCATION:1>>."

    def test_defaults_instantiate_linker_and_anonymizer(self) -> None:
        """A detector-only pipeline has an ExactEntityLinker and a label-counter Anonymizer."""
        pipeline = AnonymizationPipeline(ExactMatchDetector({"Emma": "PERSON"}))
        assert isinstance(pipeline.linker, ExactEntityLinker)
        assert isinstance(pipeline.anonymizer, Anonymizer)
        assert isinstance(pipeline.anonymizer.factory, LabelCounterPlaceholderFactory)

    async def test_all_stages_compose(self) -> None:
        """The optional resolvers and expander run without changing correctness."""
        pipeline = AnonymizationPipeline(
            ExactMatchDetector({"Emma": "PERSON"}),
            ExactEntityLinker(),
            Anonymizer(RedactPlaceholderFactory()),
            overlap_resolver=ConfidenceOverlapResolver(),
            expander=WordBoundaryExpander(),
            entity_resolver=MergeEntityResolver(),
        )
        result = await pipeline.anonymize("Emma and Emma")
        assert result.text == "<<REDACT>> and <<REDACT>>"

    async def test_no_pii_leaves_text_unchanged(self) -> None:
        """Text with nothing to detect passes through, with no tokens."""
        pipeline = AnonymizationPipeline(
            ExactMatchDetector({"Emma": "PERSON"}),
            ExactEntityLinker(),
            Anonymizer(RedactPlaceholderFactory()),
        )
        result = await pipeline.anonymize("nothing here")
        assert result.text == "nothing here"
        assert result.tokens == {}


class TestGuard:
    async def test_a_flagged_guard_raises(self) -> None:
        """A guard that still finds PII in the output raises PIIRemainingError."""
        pipeline = AnonymizationPipeline(
            ExactMatchDetector({"Emma": "PERSON"}),
            ExactEntityLinker(),
            Anonymizer(RedactPlaceholderFactory()),
            guard=DetectorGuardRail(ExactMatchDetector({"Bob": "PERSON"})),
        )
        with pytest.raises(PIIRemainingError):
            await pipeline.anonymize("Emma knows Bob")

    async def test_a_clean_guard_passes(self) -> None:
        """A guard that finds nothing lets the result through."""
        pipeline = AnonymizationPipeline(
            ExactMatchDetector({"Emma": "PERSON"}),
            ExactEntityLinker(),
            Anonymizer(RedactPlaceholderFactory()),
            guard=DetectorGuardRail(ExactMatchDetector({"Bob": "PERSON"})),
        )
        result = await pipeline.anonymize("Emma is here")
        assert result.text == "<<REDACT>> is here"


class TestDeanonymize:
    async def test_round_trips_through_deanonymize(self) -> None:
        """Deanonymizing the output restores the original text."""
        pipeline = AnonymizationPipeline(
            ExactMatchDetector({"Emma": "PERSON", "Liam": "PERSON"}),
            ExactEntityLinker(),
            Anonymizer(LabelCounterPlaceholderFactory()),
        )
        result = await pipeline.anonymize("Emma met Liam")
        restored = pipeline.deanonymize(result.text, result.tokens)
        assert restored == "Emma met Liam"


class _FixedDetector:
    """A detector returning the same detections whatever the text."""

    def __init__(self, detections: list[Detection]) -> None:
        self.detections = detections

    async def detect(self, text: str) -> list[Detection]:
        return list(self.detections)


class TestExpansion:
    async def test_an_occurrence_inside_a_detection_does_not_break_rendering(
        self,
    ) -> None:
        """The expander never adds an occurrence the renderer would refuse.

        "Paul" is found alone once, and also sits inside "Monsieur Paul", which
        is already detected. Expanding it there used to raise
        OverlappingSpansError at render time.
        """
        text = "Monsieur Paul signe. Paul arrive."
        detector = _FixedDetector(
            [
                Detection(Span(0, 13), "Monsieur Paul", "PERSON", 0.8),
                Detection(Span(21, 25), "Paul", "PERSON", 1.0),
            ]
        )
        pipeline = AnonymizationPipeline(
            detector,
            ExactEntityLinker(),
            Anonymizer(LabelCounterPlaceholderFactory()),
            expander=WordBoundaryExpander(),
        )
        result = await pipeline.anonymize(text)
        assert "Paul" not in result.text


class TestMergeOverlap:
    async def test_the_merge_resolver_leaves_no_fragment_of_a_longer_span(
        self,
    ) -> None:
        """With the merge resolver, a sure short rule span cannot uncover a model's longer one."""
        from piighost.components.overlap_resolver import MergeOverlapResolver

        text = "Signé par Loni M. Wirth."
        detector = _FixedDetector(
            [
                Detection(Span(18, 23), "Wirth", "FR_CIVIL_NAME", 1.0),
                Detection(Span(10, 23), "Loni M. Wirth", "PERSON", 0.7),
            ]
        )
        pipeline = AnonymizationPipeline(
            detector,
            ExactEntityLinker(),
            Anonymizer(LabelCounterPlaceholderFactory()),
            overlap_resolver=MergeOverlapResolver(),
        )
        result = await pipeline.anonymize(text)
        assert result.text == "Signé par <<FR_CIVIL_NAME:1>>."


class TestUnicodeSpaces:
    async def test_a_value_keeps_one_token_whatever_its_spaces(self) -> None:
        """A value detected with a no-break space and repeated with a plain one shares a token."""
        text = "Paul\u00a0Martin signe. Paul Martin paie. Paul  Martin part."
        span = Span(0, 11)
        detection = Detection(
            span=span,
            text="Paul\u00a0Martin",
            label="PERSON",
            confidence=0.9,
        )
        pipeline = AnonymizationPipeline(
            _FixedDetector([detection]),
            ExactEntityLinker(),
            Anonymizer(LabelCounterPlaceholderFactory()),
            expander=WordBoundaryExpander(),
        )
        result = await pipeline.anonymize(text)
        assert result.text == (
            "<<PERSON:1>> signe. <<PERSON:1>> paie. <<PERSON:1>> part."
        )

    async def test_a_regex_value_typed_with_no_break_spaces_is_hidden(self) -> None:
        """A pattern written for plain spaces hides a value typed with others."""
        text = "IBAN FR76\u00a03000\u202f6000\u00a00112\u00a03456\u00a07890\u00a0189."
        iban = r"\b[A-Z]{2}\d{2}(?:[\s-]?[A-Z0-9]){11,30}\b"
        pipeline = AnonymizationPipeline(RegexDetector({"IBAN": iban}))
        result = await pipeline.anonymize(text)
        assert result.text == "IBAN <<IBAN:1>>."
