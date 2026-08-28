"""Tests for the ThreadAnonymizationPipeline HITL correction method."""

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import AnyDetector, ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import (
    LabelCounterPlaceholderFactory,
    PreservesLabeledIdentityOpaque,
)
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.models import Detection, Span
from piighost.pipeline import ThreadAnonymizationPipeline


def _pipeline(
    detector: AnyDetector | None = None,
) -> ThreadAnonymizationPipeline[PreservesLabeledIdentityOpaque]:
    """Build a thread pipeline over a counter factory and in-memory backend."""
    return ThreadAnonymizationPipeline(
        detector or ExactMatchDetector({"Paris": "LOCATION"}),
        ExactEntityLinker(),
        Anonymizer(LabelCounterPlaceholderFactory()),
        InMemoryConversationMemory(),
    )


def _acme() -> list[Detection]:
    """A one-detection corrected set naming Acme at the start of the text."""
    return [Detection(span=Span(0, 4), text="Acme", label="ORG", confidence=1.0)]


class TestAnonymizeCorrected:
    async def test_adds_a_missed_value(self) -> None:
        """A corrected set adds a value the detector never found."""
        pipeline = _pipeline(ExactMatchDetector({}))
        result = await pipeline.anonymize_corrected("Acme rocks", "t1", _acme())
        assert result.text == "<<ORG:1>> rocks"

    async def test_drops_a_false_positive(self) -> None:
        """An empty corrected set leaves a mis-detected value in clear."""
        pipeline = _pipeline()
        first = await pipeline.anonymize("Visit Paris", "t1")
        assert first.text == "Visit <<LOCATION:1>>"
        corrected = await pipeline.anonymize_corrected("Visit Paris", "t1", [])
        assert corrected.text == "Visit Paris"

    async def test_added_value_is_deanonymizable_thread_wide(self) -> None:
        """A corrected addition enters the thread token map and is reversible."""
        pipeline = _pipeline(ExactMatchDetector({}))
        await pipeline.anonymize_corrected("Acme rocks", "t1", _acme())
        restored = await pipeline.deanonymize("<<ORG:1>>", "t1")
        assert restored == "Acme"

    async def test_correction_is_local_to_the_message(self) -> None:
        """Dropping a value from one message does not clear it in another."""
        pipeline = _pipeline()
        await pipeline.anonymize("Visit Paris", "t1")
        await pipeline.anonymize_corrected("Visit Paris", "t1", [])
        later = await pipeline.anonymize("Go to Paris", "t1")
        assert later.text == "Go to <<LOCATION:1>>"

    async def test_re_correcting_replaces_cleanly(self) -> None:
        """A second corrected set replaces the first rather than merging."""
        pipeline = _pipeline(ExactMatchDetector({}))
        await pipeline.anonymize_corrected("Acme rocks", "t1", _acme())
        replaced = await pipeline.anonymize_corrected("Acme rocks", "t1", [])
        assert replaced.text == "Acme rocks"
