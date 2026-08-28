"""Tests for the ThreadAnonymizationPipeline."""

import pytest

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import AnyDetector, ExactMatchDetector
from piighost.components.guard import DetectorGuardRail
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import (
    LabelCounterPlaceholderFactory,
    PreservesLabeledIdentityOpaque,
)
from piighost.conversation_memory import InMemoryConversationMemory, MessageRole
from piighost.models import Detection
from piighost.pipeline import ThreadAnonymizationPipeline


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
) -> ThreadAnonymizationPipeline[PreservesLabeledIdentityOpaque]:
    """Build a thread pipeline over a counter factory and in-memory backend."""
    return ThreadAnonymizationPipeline(
        detector or ExactMatchDetector({"Emma": "PERSON", "Liam": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(LabelCounterPlaceholderFactory()),
        memory or InMemoryConversationMemory(),
    )


class TestDefaults:
    def test_builds_from_a_detector_alone(self) -> None:
        """Omitting linker, anonymizer, and memory builds their defaults."""
        detector = ExactMatchDetector({"Emma": "PERSON"})
        pipeline = ThreadAnonymizationPipeline(detector)
        assert isinstance(pipeline.linker, ExactEntityLinker)
        assert isinstance(pipeline.anonymizer, Anonymizer)
        assert isinstance(pipeline.memory, InMemoryConversationMemory)

    async def test_the_default_pipeline_stays_thread_stable(self) -> None:
        """The detector-only pipeline tokenizes and keeps tokens across a thread."""
        detector = ExactMatchDetector({"Emma": "PERSON"})
        pipeline = ThreadAnonymizationPipeline(detector)
        first = await pipeline.anonymize("Hello Emma", "t1")
        second = await pipeline.anonymize("Bye Emma", "t1")
        assert first.text == "Hello <<PERSON:1>>"
        assert second.text == "Bye <<PERSON:1>>"

    def test_each_pipeline_gets_its_own_memory(self) -> None:
        """The default memory is built per instance, not shared across pipelines."""
        detector = ExactMatchDetector({"Emma": "PERSON"})
        one = ThreadAnonymizationPipeline(detector)
        two = ThreadAnonymizationPipeline(detector)
        assert one.memory is not two.memory


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
    async def test_round_trips_a_message_from_the_thread(self) -> None:
        """Deanonymizing a message's output restores its original text."""
        pipeline = _pipeline()
        result = await pipeline.anonymize("Emma met Liam", "t1")
        restored = await pipeline.deanonymize(result.text, "t1")
        assert restored == "Emma met Liam"

    async def test_restores_tokens_the_pipeline_never_anonymized(self) -> None:
        """A reply built from thread tokens is restored, though never anonymized."""
        pipeline = _pipeline()
        await pipeline.anonymize("Emma met Liam", "t1")
        reply = "Thanks <<PERSON:1>> and <<PERSON:2>>."
        assert await pipeline.deanonymize(reply, "t1") == "Thanks Emma and Liam."


class TestThreadTokenMap:
    async def test_maps_each_token_to_its_value(self) -> None:
        """The map pairs every thread token with the value it restores to."""
        pipeline = _pipeline()
        await pipeline.anonymize("Emma met Liam", "t1")
        assert await pipeline.thread_token_map("t1") == {
            "<<PERSON:1>>": "Emma",
            "<<PERSON:2>>": "Liam",
        }

    async def test_an_untouched_thread_has_an_empty_map(self) -> None:
        """A thread with nothing anonymized yet maps to nothing."""
        pipeline = _pipeline()
        assert await pipeline.thread_token_map("empty") == {}

    async def test_matches_what_deanonymize_restores(self) -> None:
        """Replacing a text through the map yields what deanonymize would."""
        pipeline = _pipeline()
        result = await pipeline.anonymize("Emma met Liam", "t1")
        token_map = await pipeline.thread_token_map("t1")

        rebuilt = result.text
        for token, value in token_map.items():
            rebuilt = rebuilt.replace(token, value)
        assert rebuilt == await pipeline.deanonymize(result.text, "t1")


class TestProvenance:
    async def test_assistant_introduced_value_stays_clear(self) -> None:
        """A value the assistant introduces first is not anonymized."""
        pipeline = _pipeline()
        result = await pipeline.anonymize("It is Emma", "t1", MessageRole.ASSISTANT)
        assert result.text == "It is Emma"

    async def test_user_reference_after_assistant_stays_clear(self) -> None:
        """A user reference to an assistant-introduced value stays in clear."""
        pipeline = _pipeline()
        await pipeline.anonymize("It is Emma", "t1", MessageRole.ASSISTANT)
        result = await pipeline.anonymize("what about Emma", "t1", MessageRole.USER)
        assert result.text == "what about Emma"

    async def test_user_introduced_value_is_anonymized(self) -> None:
        """A value the user introduces first is anonymized as before."""
        pipeline = _pipeline()
        result = await pipeline.anonymize("I am Emma", "t1", MessageRole.USER)
        assert result.text == "I am <<PERSON:1>>"

    async def test_assistant_repeat_after_user_stays_anonymized(self) -> None:
        """A user-introduced value stays anonymized when the assistant repeats it."""
        pipeline = _pipeline()
        await pipeline.anonymize("I am Emma", "t1", MessageRole.USER)
        result = await pipeline.anonymize("Hello Emma", "t1", MessageRole.ASSISTANT)
        assert result.text == "Hello <<PERSON:1>>"

    async def test_default_role_anonymizes(self) -> None:
        """Omitting the role treats the message as user PII."""
        pipeline = _pipeline()
        result = await pipeline.anonymize("I am Emma", "t1")
        assert result.text == "I am <<PERSON:1>>"

    async def test_a_guard_does_not_flag_a_preserved_value(self) -> None:
        """A preserved assistant value is exempt from the guard, not flagged."""
        memory = InMemoryConversationMemory()
        pipeline = ThreadAnonymizationPipeline(
            ExactMatchDetector({"Emma": "PERSON", "Liam": "PERSON"}),
            ExactEntityLinker(),
            Anonymizer(LabelCounterPlaceholderFactory()),
            memory,
            guard=DetectorGuardRail(ExactMatchDetector({"Emma": "PERSON"})),
        )
        result = await pipeline.anonymize("It is Emma", "t1", MessageRole.ASSISTANT)
        assert result.text == "It is Emma"

    async def test_a_guard_still_flags_real_residual_pii(self) -> None:
        """A residual value that was not preserved still trips the guard."""
        from piighost.exceptions import PIIRemainingError

        memory = InMemoryConversationMemory()
        pipeline = ThreadAnonymizationPipeline(
            ExactMatchDetector({"Emma": "PERSON"}),
            ExactEntityLinker(),
            Anonymizer(LabelCounterPlaceholderFactory()),
            memory,
            guard=DetectorGuardRail(ExactMatchDetector({"Liam": "PERSON"})),
        )
        with pytest.raises(PIIRemainingError):
            await pipeline.anonymize("Liam is here", "t1", MessageRole.ASSISTANT)
