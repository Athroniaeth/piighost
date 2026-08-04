"""Integration tests for the override stage in both pipelines."""

import pytest

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.guard import DetectorGuardRail
from piighost.components.linker import ExactEntityLinker
from piighost.components.override import (
    BlacklistStrategy,
    DetectionOverride,
    WhitelistStrategy,
)
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.conversation_memory import InMemoryConversationMemory, MessageRole
from piighost.exceptions import PIIRemainingError
from piighost.models import Detection, Span
from piighost.pipeline import AnonymizationPipeline, ThreadAnonymizationPipeline


def _pipeline(
    detector: ExactMatchDetector,
    override: DetectionOverride,
    guard: DetectorGuardRail | None = None,
) -> AnonymizationPipeline:
    """Build a base pipeline with an override and an optional guard."""
    return AnonymizationPipeline(
        detector,
        ExactEntityLinker(),
        Anonymizer(LabelCounterPlaceholderFactory()),
        guard=guard,
        override=override,
    )


class TestBasePipelineOverride:
    async def test_whitelist_forces_a_value_the_detector_missed(self) -> None:
        """A whitelisted value is anonymized though the detector never saw it."""
        override = DetectionOverride(whitelist=ExactMatchDetector({"Acme": "ORG"}))
        pipeline = _pipeline(ExactMatchDetector({}), override)
        result = await pipeline.anonymize("Acme rocks")
        assert result.text == "<<ORG:1>> rocks"

    async def test_blacklist_keeps_a_false_positive_in_clear(self) -> None:
        """A blacklisted value the detector flags stays in clear."""
        override = DetectionOverride(
            blacklist=ExactMatchDetector({"Paris": "LOCATION"})
        )
        pipeline = _pipeline(ExactMatchDetector({"Paris": "LOCATION"}), override)
        result = await pipeline.anonymize("Visit Paris")
        assert result.text == "Visit Paris"

    async def test_blacklisted_value_does_not_trip_the_guard(self) -> None:
        """A guard that knows the blacklisted value exempts it, by design."""
        override = DetectionOverride(
            blacklist=ExactMatchDetector({"Paris": "LOCATION"}),
            blacklist_strategy=BlacklistStrategy.VALUE,
        )
        guard = DetectorGuardRail(ExactMatchDetector({"Paris": "LOCATION"}))
        pipeline = _pipeline(ExactMatchDetector({"Emma": "PERSON"}), override, guard)
        result = await pipeline.anonymize("Emma visits Paris")
        assert result.text == "<<PERSON:1>> visits Paris"

    async def test_a_real_leak_still_trips_the_guard(self) -> None:
        """The exemption covers the blacklist only, other leaks still refuse."""
        override = DetectionOverride(
            blacklist=ExactMatchDetector({"Paris": "LOCATION"})
        )
        guard = DetectorGuardRail(ExactMatchDetector({"leak@x.com": "EMAIL"}))
        pipeline = _pipeline(ExactMatchDetector({"Emma": "PERSON"}), override, guard)
        with pytest.raises(PIIRemainingError):
            await pipeline.anonymize("Emma wrote leak@x.com")


class TestThreadPipelineOverride:
    async def test_whitelist_trumps_a_hitl_drop(self) -> None:
        """A correction removing a whitelisted value sees it re-imposed."""
        override = DetectionOverride(whitelist=ExactMatchDetector({"Emma": "PERSON"}))
        pipeline = ThreadAnonymizationPipeline(
            ExactMatchDetector({}),
            ExactEntityLinker(),
            Anonymizer(LabelCounterPlaceholderFactory()),
            InMemoryConversationMemory(),
            override=override,
        )
        result = await pipeline.anonymize_corrected("Hi Emma", "t1", [])
        assert result.text == "Hi <<PERSON:1>>"

    async def test_blacklist_trumps_a_hitl_add(self) -> None:
        """A correction adding a blacklisted value sees it cleared."""
        override = DetectionOverride(
            blacklist=ExactMatchDetector({"Paris": "LOCATION"})
        )
        pipeline = ThreadAnonymizationPipeline(
            ExactMatchDetector({}),
            ExactEntityLinker(),
            Anonymizer(LabelCounterPlaceholderFactory()),
            InMemoryConversationMemory(),
            override=override,
        )
        added = Detection(
            span=Span(6, 11),
            text="Paris",
            label="LOCATION",
            confidence=1.0,
        )
        result = await pipeline.anonymize_corrected("Visit Paris", "t1", [added])
        assert result.text == "Visit Paris"

    async def test_whitelisted_value_is_deanonymizable(self) -> None:
        """A forced value enters the thread token map and restores."""
        override = DetectionOverride(whitelist=ExactMatchDetector({"Emma": "PERSON"}))
        pipeline = ThreadAnonymizationPipeline(
            ExactMatchDetector({}),
            ExactEntityLinker(),
            Anonymizer(LabelCounterPlaceholderFactory()),
            InMemoryConversationMemory(),
            override=override,
        )
        await pipeline.anonymize("Hi Emma", "t1")
        restored = await pipeline.deanonymize("<<PERSON:1>>", "t1")
        assert restored == "Emma"

    async def test_blacklist_clears_a_fresh_thread_detection(self) -> None:
        """A blacklisted value the detector finds on a fresh message stays clear."""
        override = DetectionOverride(
            blacklist=ExactMatchDetector({"Paris": "LOCATION"})
        )
        pipeline = ThreadAnonymizationPipeline(
            ExactMatchDetector({"Paris": "LOCATION"}),
            ExactEntityLinker(),
            Anonymizer(LabelCounterPlaceholderFactory()),
            InMemoryConversationMemory(),
            override=override,
        )
        result = await pipeline.anonymize("Visit Paris", "t1")
        assert result.text == "Visit Paris"
        restored = await pipeline.deanonymize("Visit Paris", "t1")
        assert restored == "Visit Paris"

    async def test_assistant_introduced_whitelisted_value_stays_clear(self) -> None:
        """By default, provenance outranks the whitelist for tokenization."""
        override = DetectionOverride(whitelist=ExactMatchDetector({"Acme": "ORG"}))
        pipeline = ThreadAnonymizationPipeline(
            ExactMatchDetector({}),
            ExactEntityLinker(),
            Anonymizer(LabelCounterPlaceholderFactory()),
            InMemoryConversationMemory(),
            override=override,
        )
        first = await pipeline.anonymize("Acme rocks", "t1", MessageRole.ASSISTANT)
        later = await pipeline.anonymize("I love Acme", "t1")
        assert first.text == "Acme rocks"
        assert later.text == "I love Acme"

    async def test_force_strategy_outranks_assistant_provenance(self) -> None:
        """Under FORCE, a whitelisted value is tokenized whoever introduced it."""
        override = DetectionOverride(
            whitelist=ExactMatchDetector({"Acme": "ORG"}),
            whitelist_strategy=WhitelistStrategy.FORCE,
        )
        pipeline = ThreadAnonymizationPipeline(
            ExactMatchDetector({}),
            ExactEntityLinker(),
            Anonymizer(LabelCounterPlaceholderFactory()),
            InMemoryConversationMemory(),
            override=override,
        )
        first = await pipeline.anonymize("Acme rocks", "t1", MessageRole.ASSISTANT)
        later = await pipeline.anonymize("I love Acme", "t1")
        assert first.text == "<<ORG:1>> rocks"
        assert later.text == "I love <<ORG:1>>"
