"""Tests for the AnonymizationPipeline, wired from real components."""

import pytest

from piighost.anonymizer import Anonymizer
from piighost.detector import ExactMatchDetector
from piighost.entity_resolver import MergeEntityResolver
from piighost.exceptions import PIIRemainingError
from piighost.expander import WordBoundaryExpander
from piighost.guard import DetectorGuardRail
from piighost.linker import ExactEntityLinker
from piighost.overlap_resolver import ConfidenceOverlapResolver
from piighost.pipeline import AnonymizationPipeline
from piighost.placeholder import (
    LabelCounterPlaceholderFactory,
    RedactPlaceholderFactory,
)


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

    async def test_repeats_group_into_one_token(self) -> None:
        """A value seen twice links to one entity and one token."""
        pipeline = AnonymizationPipeline(
            ExactMatchDetector({"Emma": "PERSON"}),
            ExactEntityLinker(),
            Anonymizer(LabelCounterPlaceholderFactory()),
        )
        result = await pipeline.anonymize("Emma and Emma")
        assert result.text == "<<PERSON:1>> and <<PERSON:1>>"

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
