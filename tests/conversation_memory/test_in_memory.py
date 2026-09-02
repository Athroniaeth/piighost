"""Tests for the in-memory conversation memory."""

from piighost.conversation_memory import (
    AnyConversationMemory,
    Forgotten,
    InMemoryConversationMemory,
    MessageRole,
)
from piighost.models import Detection, Span


def _detection(text: str, label: str = "PERSON") -> Detection:
    """Build a detection for the given text and label at a dummy span."""
    return Detection(span=Span(0, len(text)), text=text, label=label, confidence=0.9)


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """InMemoryConversationMemory is an AnyConversationMemory."""
        assert isinstance(InMemoryConversationMemory(), AnyConversationMemory)


class TestGetDetectionsForAMessage:
    async def test_returns_the_detections_of_a_known_message(self) -> None:
        """Passing a message returns the detections cached for it."""
        memory = InMemoryConversationMemory()
        emma = _detection("Emma")
        await memory.remember("t1", "I am Emma", [emma])
        assert await memory.get_detections("t1", "I am Emma") == [emma]

    async def test_unknown_message_is_a_miss(self) -> None:
        """A message never remembered returns None, not an empty list."""
        memory = InMemoryConversationMemory()
        await memory.remember("t1", "I am Emma", [_detection("Emma")])
        assert await memory.get_detections("t1", "who is this") is None

    async def test_a_clean_message_is_a_hit_with_no_detections(self) -> None:
        """A remembered message with no PII returns an empty list, not None."""
        memory = InMemoryConversationMemory()
        await memory.remember("t1", "hello there", [])
        assert await memory.get_detections("t1", "hello there") == []

    async def test_remembering_a_message_again_overwrites(self) -> None:
        """Re-remembering the same message replaces its cached detections."""
        memory = InMemoryConversationMemory()
        await memory.remember("t1", "I am Emma", [_detection("Emma")])
        liam = _detection("Liam")
        await memory.remember("t1", "I am Emma", [liam])
        assert await memory.get_detections("t1", "I am Emma") == [liam]

    async def test_message_in_unknown_thread_is_a_miss(self) -> None:
        """Asking for a message in a thread never written to returns None."""
        memory = InMemoryConversationMemory()
        assert await memory.get_detections("never", "anything") is None


class TestGetDetectionsUnion:
    async def test_no_message_unions_detections_in_first_seen_order(self) -> None:
        """Omitting the message flattens every message's detections in order."""
        memory = InMemoryConversationMemory()
        emma = _detection("Emma")
        liam = _detection("Liam")
        await memory.remember("t1", "m1", [emma])
        await memory.remember("t1", "m2", [liam])
        assert await memory.get_detections("t1") == [emma, liam]

    async def test_explicit_none_means_the_whole_thread(self) -> None:
        """Passing None as the message is the same as omitting it."""
        memory = InMemoryConversationMemory()
        emma = _detection("Emma")
        await memory.remember("t1", "m1", [emma])
        assert await memory.get_detections("t1", None) == [emma]

    async def test_unknown_thread_has_no_detections(self) -> None:
        """A thread never written to yields an empty union."""
        memory = InMemoryConversationMemory()
        assert await memory.get_detections("never") == []


class TestThreadIsolation:
    async def test_threads_do_not_leak_into_each_other(self) -> None:
        """Detections in one thread never appear in another."""
        memory = InMemoryConversationMemory()
        emma = _detection("Emma")
        liam = _detection("Liam")
        await memory.remember("t1", "m1", [emma])
        await memory.remember("t2", "m1", [liam])
        assert await memory.get_detections("t1") == [emma]
        assert await memory.get_detections("t2", "m1") == [liam]


class TestForget:
    async def test_forget_purges_a_thread(self) -> None:
        """Forgetting a thread drops its detections and its message cache."""
        memory = InMemoryConversationMemory()
        await memory.remember("t1", "m1", [_detection("Emma")])
        await memory.forget("t1")
        assert await memory.get_detections("t1") == []
        assert await memory.get_detections("t1", "m1") is None

    async def test_forget_reports_what_it_erased(self) -> None:
        """Forgetting reports how many messages and detections were dropped."""
        memory = InMemoryConversationMemory()
        await memory.remember("t1", "m1", [_detection("Emma"), _detection("Liam")])
        await memory.remember("t1", "m2", [_detection("Noah")])
        assert await memory.forget("t1") == Forgotten(messages=2, detections=3)

    async def test_forget_unknown_thread_reports_nothing_erased(self) -> None:
        """Forgetting a thread never written reports zero and raises nothing."""
        memory = InMemoryConversationMemory()
        assert await memory.forget("never") == Forgotten(0, 0)

    async def test_forget_leaves_other_threads_intact(self) -> None:
        """Forgetting one thread does not touch another."""
        memory = InMemoryConversationMemory()
        liam = _detection("Liam")
        await memory.remember("t1", "m1", [_detection("Emma")])
        await memory.remember("t2", "m1", [liam])
        await memory.forget("t1")
        assert await memory.get_detections("t2") == [liam]


class TestEncapsulation:
    async def test_returned_union_is_a_copy(self) -> None:
        """Mutating the returned union does not corrupt the stored detections."""
        memory = InMemoryConversationMemory()
        emma = _detection("Emma")
        await memory.remember("t1", "m1", [emma])
        union = await memory.get_detections("t1")
        assert union is not None
        union.append(_detection("Liam"))
        assert await memory.get_detections("t1") == [emma]

    async def test_remember_copies_its_input(self) -> None:
        """Mutating the list passed to remember does not change the store."""
        memory = InMemoryConversationMemory()
        emma = _detection("Emma")
        given = [emma]
        await memory.remember("t1", "m1", given)
        given.append(_detection("Liam"))
        assert await memory.get_detections("t1", "m1") == [emma]


class TestBounding:
    async def test_reading_an_unknown_thread_creates_no_entry(self) -> None:
        """A read of an unknown thread does not evict a real one (no phantom entry)."""
        memory = InMemoryConversationMemory(max_threads=1)
        emma = _detection("Emma")
        await memory.remember("t1", "m1", [emma])
        # A read of a never-written thread must not count as a thread.
        assert await memory.get_detections("ghost") == []
        assert await memory.get_provenance("ghost") == {}
        assert await memory.get_detections("t1") == [emma]

    async def test_max_threads_evicts_least_recently_used(self) -> None:
        """Past max_threads, the least recently used thread is dropped."""
        memory = InMemoryConversationMemory(max_threads=2)
        await memory.remember("t1", "m1", [_detection("Emma")])
        await memory.remember("t2", "m1", [_detection("Liam")])
        await memory.remember("t3", "m1", [_detection("Noah")])
        assert await memory.get_detections("t1") == []
        assert await memory.get_detections("t2") == [_detection("Liam")]
        assert await memory.get_detections("t3") == [_detection("Noah")]

    async def test_access_refreshes_recency(self) -> None:
        """Reading a thread marks it recently used, sparing it from eviction."""
        memory = InMemoryConversationMemory(max_threads=2)
        await memory.remember("t1", "m1", [_detection("Emma")])
        await memory.remember("t2", "m1", [_detection("Liam")])
        await memory.get_detections("t1")  # t1 is now most recent
        await memory.remember("t3", "m1", [_detection("Noah")])
        assert await memory.get_detections("t1") == [_detection("Emma")]
        assert await memory.get_detections("t2") == []

    async def test_ttl_expires_a_thread_lazily(self) -> None:
        """A thread older than the ttl is dropped on the next access."""
        clock = {"now": 1000.0}
        memory = InMemoryConversationMemory(ttl=60.0, time_source=lambda: clock["now"])
        await memory.remember("t1", "m1", [_detection("Emma")])
        clock["now"] = 1070.0  # 70s later, past the 60s ttl
        assert await memory.get_detections("t1") == []
        assert await memory.get_detections("t1", "m1") is None


class TestProvenance:
    async def test_records_the_role_of_a_first_occurrence(self) -> None:
        """A value's provenance is the role of the message that first held it."""
        memory = InMemoryConversationMemory()
        await memory.remember(
            "t1", "a1", [_detection("Napoleon")], MessageRole.ASSISTANT
        )
        assert await memory.get_provenance("t1") == {"napoleon": MessageRole.ASSISTANT}

    async def test_first_occurrence_wins(self) -> None:
        """A later message with the same value does not change its provenance."""
        memory = InMemoryConversationMemory()
        await memory.remember("t1", "u1", [_detection("Napoleon")], MessageRole.USER)
        await memory.remember(
            "t1", "a1", [_detection("Napoleon")], MessageRole.ASSISTANT
        )
        assert await memory.get_provenance("t1") == {"napoleon": MessageRole.USER}

    async def test_provenance_folds_case(self) -> None:
        """Case variants of a value share one provenance entry."""
        memory = InMemoryConversationMemory()
        await memory.remember(
            "t1", "a1", [_detection("Napoleon")], MessageRole.ASSISTANT
        )
        await memory.remember("t1", "u1", [_detection("napoleon")], MessageRole.USER)
        assert await memory.get_provenance("t1") == {"napoleon": MessageRole.ASSISTANT}

    async def test_default_role_is_user(self) -> None:
        """Remembering without a role records USER provenance."""
        memory = InMemoryConversationMemory()
        await memory.remember("t1", "u1", [_detection("Emma")])
        assert await memory.get_provenance("t1") == {"emma": MessageRole.USER}

    async def test_unknown_thread_has_no_provenance(self) -> None:
        """A thread never written to yields an empty provenance map."""
        memory = InMemoryConversationMemory()
        assert await memory.get_provenance("never") == {}
