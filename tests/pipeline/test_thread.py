"""Tests for the ThreadAnonymizationPipeline."""

from piighost.anonymizer import Anonymizer
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.detector import AnyDetector, ExactMatchDetector
from piighost.linker import ExactEntityLinker
from piighost.models import Detection
from piighost.pipeline import ThreadAnonymizationPipeline
from piighost.placeholder import LabelCounterPlaceholderFactory


class _CountingDetector:
    """Wrap a detector to count how many times detection actually runs."""

    def __init__(self, inner: AnyDetector) -> None:
        self.inner = inner
        self.calls = 0

    async def detect(self, text: str) -> list[Detection]:
        """Count the call and delegate to the wrapped detector."""
        self.calls += 1
        return await self.inner.detect(text)


def _pipeline(
    detector: AnyDetector | None = None,
    memory: InMemoryConversationMemory | None = None,
) -> ThreadAnonymizationPipeline:
    """Build a thread pipeline over a counter factory and in-memory backend."""
    return ThreadAnonymizationPipeline(
        detector or ExactMatchDetector({"Emma": "PERSON", "Liam": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(LabelCounterPlaceholderFactory()),
        memory or InMemoryConversationMemory(),
    )


class TestThreadConsistency:
    async def test_a_value_keeps_its_token_across_messages(self) -> None:
        """A name seen in two messages of one thread gets the same token."""
        pipeline = _pipeline()
        first = await pipeline.anonymize("Hello Emma", "t1")
        second = await pipeline.anonymize("Bye Emma", "t1")
        assert first.text == "Hello <<PERSON:1>>"
        assert second.text == "Bye <<PERSON:1>>"

    async def test_a_new_value_gets_the_next_number(self) -> None:
        """A value first seen in a later message numbers after earlier ones."""
        pipeline = _pipeline()
        await pipeline.anonymize("Emma", "t1")
        second = await pipeline.anonymize("Emma and Liam", "t1")
        assert second.text == "<<PERSON:1>> and <<PERSON:2>>"

    async def test_threads_are_isolated(self) -> None:
        """Each thread numbers from one, unaffected by another thread."""
        pipeline = _pipeline()
        in_a = await pipeline.anonymize("Liam", "a")
        in_b = await pipeline.anonymize("Emma", "b")
        assert in_a.text == "<<PERSON:1>>"
        assert in_b.text == "<<PERSON:1>>"


class TestCache:
    async def test_resending_a_message_skips_detection(self) -> None:
        """A message seen before reuses its cached detections."""
        detector = _CountingDetector(ExactMatchDetector({"Emma": "PERSON"}))
        pipeline = _pipeline(detector=detector)
        await pipeline.anonymize("Hello Emma", "t1")
        await pipeline.anonymize("Hello Emma", "t1")
        assert detector.calls == 1


class TestForget:
    async def test_forget_thread_clears_the_memory(self) -> None:
        """Forgetting a thread erases its messages and empties its union."""
        memory = InMemoryConversationMemory()
        pipeline = _pipeline(memory=memory)
        await pipeline.anonymize("Emma and Liam", "t1")
        forgotten = await pipeline.forget_thread("t1")
        assert forgotten.messages == 1
        assert await memory.get_detections("t1") == []


class TestDeanonymize:
    async def test_round_trips_through_deanonymize(self) -> None:
        """Deanonymizing a message's output restores its original text."""
        pipeline = _pipeline()
        result = await pipeline.anonymize("Emma met Liam", "t1")
        restored = pipeline.deanonymize(result.text, result.tokens)
        assert restored == "Emma met Liam"
