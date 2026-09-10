"""Tests for the ThreadAnonymizationPipeline."""

import asyncio

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
from piighost.models import Detection, Entity
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


class _GatedMemory(InMemoryConversationMemory):
    """An in-memory backend whose provenance read can be suspended.

    It stands in for a networked backend, where a derivation straddles an await
    and another request can complete in between.
    """

    def __init__(self) -> None:
        """Start open, so a read only blocks once the gate is closed."""
        super().__init__()
        self.gate = asyncio.Event()
        self.gate.set()

    async def get_provenance(self, thread_id: str) -> dict[str, MessageRole]:
        """Read the provenance, then wait on the gate before returning it."""
        provenance = await super().get_provenance(thread_id)
        await self.gate.wait()
        return provenance


class _CountingResolver:
    """An entity resolver that counts its calls and passes entities through."""

    def __init__(self) -> None:
        self.calls = 0

    def resolve(self, entities: list[Entity]) -> list[Entity]:
        """Count the call and return the entities unchanged."""
        self.calls += 1
        return entities


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


def _resolving_pipeline(
    resolver: _CountingResolver,
) -> ThreadAnonymizationPipeline[PreservesLabeledIdentityOpaque]:
    """Build a thread pipeline whose entity resolver counts its calls.

    The count is how many times the thread's token map was derived rather than
    read back from the memo, which is the only outward sign the memo was used.
    """
    return ThreadAnonymizationPipeline(
        ExactMatchDetector({"Emma": "PERSON", "Liam": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(LabelCounterPlaceholderFactory()),
        InMemoryConversationMemory(),
        entity_resolver=resolver,
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

    async def test_forget_thread_drops_the_memoized_tokens(self) -> None:
        """Replaying a forgotten thread's message derives its tokens afresh.

        The memoized token map holds the thread's entities in clear, so erasing
        the store alone would keep a forgotten thread's PII live in the process.
        A reused map is observable: the same message replayed after the erasure
        rebuilds the identical memo key, so a surviving entry would be a hit and
        the resolver would not run again.
        """
        resolver = _CountingResolver()
        pipeline = _resolving_pipeline(resolver)
        await pipeline.anonymize("Hi Emma", "t1")
        assert resolver.calls == 1
        await pipeline.forget_thread("t1")
        await pipeline.anonymize("Hi Emma", "t1")
        assert resolver.calls == 2

    async def test_an_erasure_mid_derivation_is_not_memoized(self) -> None:
        """A derivation straddling an erasure returns, but memoizes nothing.

        The token map is derived across awaits, so a request already in flight
        can finish after the erasure. Memoizing its result would put the erased
        thread's values back in the memo, where they would sit until eviction.
        """
        memory = _GatedMemory()
        pipeline = _pipeline(memory=memory)
        await pipeline.anonymize("Hi Emma", "t1")

        memory.gate.clear()
        inflight = asyncio.create_task(pipeline.anonymize("Emma again", "t1"))
        await asyncio.sleep(0)
        await pipeline.forget_thread("t1")

        memory.gate.set()
        result = await inflight
        assert result.text == "<<PERSON:1>> again"
        assert not pipeline._token_memo

    async def test_forget_thread_keeps_another_thread_memoized(self) -> None:
        """Forgetting one thread leaves another thread's token map memoized."""
        resolver = _CountingResolver()
        pipeline = _resolving_pipeline(resolver)
        await pipeline.anonymize("Hi Emma", "t1")
        await pipeline.anonymize("Hi Emma", "t2")
        assert resolver.calls == 2
        await pipeline.forget_thread("t1")
        await pipeline.deanonymize("<<PERSON:1>>", "t2")
        assert resolver.calls == 2


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


class TestTokenMemoTtl:
    """The ttl bounding how long a memoized token map holds its thread's values."""

    def _ttl_pipeline(
        self, clock: list[float], resolver: _CountingResolver
    ) -> ThreadAnonymizationPipeline[PreservesLabeledIdentityOpaque]:
        """Build a thread pipeline whose memo ttl reads an injectable clock."""
        return ThreadAnonymizationPipeline(
            ExactMatchDetector({"Emma": "PERSON", "Liam": "PERSON"}),
            ExactEntityLinker(),
            Anonymizer(LabelCounterPlaceholderFactory()),
            InMemoryConversationMemory(),
            token_memo_ttl=60.0,
            time_source=lambda: clock[0],
            entity_resolver=resolver,
        )

    async def test_an_entry_is_reused_until_its_deadline(self) -> None:
        """Before the ttl passes, the memoized token map is still reused."""
        clock, resolver = [0.0], _CountingResolver()
        pipeline = self._ttl_pipeline(clock, resolver)
        await pipeline.anonymize("Hi Emma", "t1")
        clock[0] = 59.0
        assert await pipeline.deanonymize("<<PERSON:1>>", "t1") == "Emma"
        assert resolver.calls == 1

    async def test_an_expired_entry_is_derived_again(self) -> None:
        """Past the ttl the map is dropped, so restoring derives it afresh."""
        clock, resolver = [0.0], _CountingResolver()
        pipeline = self._ttl_pipeline(clock, resolver)
        await pipeline.anonymize("Hi Emma", "t1")
        clock[0] = 61.0
        assert await pipeline.deanonymize("<<PERSON:1>>", "t1") == "Emma"
        assert resolver.calls == 2

    async def test_a_sweep_drops_an_untouched_thread_s_expired_entry(self) -> None:
        """Work on one thread expires another thread's stale map, unasked.

        Retention has no behavioural surface, hence the reach into the memo: a
        dropped entry is still derivable from the store, so nothing outward
        changes. It is the point of the ttl all the same. A thread that gains a
        message derives a new key, so an older generation's entry is never
        looked up again and a lazy per-key check would never reach it.
        """
        clock, resolver = [0.0], _CountingResolver()
        pipeline = self._ttl_pipeline(clock, resolver)
        await pipeline.anonymize("Hi Emma", "t1")
        clock[0] = 61.0
        await pipeline.anonymize("and Liam", "t2")
        held = [
            entity.text for tokens in pipeline._token_memo.values() for entity in tokens
        ]
        assert held == ["Liam"]

    async def test_an_unset_ttl_keeps_the_entry(self) -> None:
        """Without a ttl, an entry lives until the size bound evicts it."""
        resolver = _CountingResolver()
        pipeline = _resolving_pipeline(resolver)
        await pipeline.anonymize("Hi Emma", "t1")
        await pipeline.deanonymize("<<PERSON:1>>", "t1")
        assert resolver.calls == 1


class TestThreadTokenMemoization:
    async def test_repeated_calls_reuse_the_thread_token_map(self) -> None:
        """Once the thread state is fixed, its token map is derived only once."""
        resolver = _CountingResolver()
        pipeline = _resolving_pipeline(resolver)
        await pipeline.anonymize("Hi Emma", "t1")
        assert resolver.calls == 1
        await pipeline.deanonymize("<<PERSON:1>>", "t1")
        await pipeline.deanonymize("<<PERSON:1>>", "t1")
        await pipeline.thread_token_map("t1")
        assert resolver.calls == 1

    async def test_a_new_message_refreshes_the_map(self) -> None:
        """A message that changes the thread's detections recomputes the map."""
        resolver = _CountingResolver()
        pipeline = _resolving_pipeline(resolver)
        await pipeline.anonymize("Hi Emma", "t1")
        await pipeline.anonymize("and Liam", "t1")
        assert resolver.calls == 2
