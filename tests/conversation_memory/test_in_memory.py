"""Tests for the in-memory conversation memory."""

from piighost.conversation_memory import (
    AnyConversationMemory,
    Forgotten,
    InMemoryConversationMemory,
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
    def test_returns_the_detections_of_a_known_message(self) -> None:
        """Passing a message returns the detections cached for it."""
        memory = InMemoryConversationMemory()
        emma = _detection("Emma")
        memory.remember("t1", "I am Emma", [emma])
        assert memory.get_detections("t1", "I am Emma") == [emma]

    def test_unknown_message_is_a_miss(self) -> None:
        """A message never remembered returns None, not an empty list."""
        memory = InMemoryConversationMemory()
        memory.remember("t1", "I am Emma", [_detection("Emma")])
        assert memory.get_detections("t1", "who is this") is None

    def test_a_clean_message_is_a_hit_with_no_detections(self) -> None:
        """A remembered message with no PII returns an empty list, not None."""
        memory = InMemoryConversationMemory()
        memory.remember("t1", "hello there", [])
        assert memory.get_detections("t1", "hello there") == []

    def test_remembering_a_message_again_overwrites(self) -> None:
        """Re-remembering the same message replaces its cached detections."""
        memory = InMemoryConversationMemory()
        memory.remember("t1", "I am Emma", [_detection("Emma")])
        liam = _detection("Liam")
        memory.remember("t1", "I am Emma", [liam])
        assert memory.get_detections("t1", "I am Emma") == [liam]

    def test_message_in_unknown_thread_is_a_miss(self) -> None:
        """Asking for a message in a thread never written to returns None."""
        assert InMemoryConversationMemory().get_detections("never", "anything") is None


class TestGetDetectionsUnion:
    def test_no_message_unions_detections_in_first_seen_order(self) -> None:
        """Omitting the message flattens every message's detections in order."""
        memory = InMemoryConversationMemory()
        emma = _detection("Emma")
        liam = _detection("Liam")
        memory.remember("t1", "m1", [emma])
        memory.remember("t1", "m2", [liam])
        assert memory.get_detections("t1") == [emma, liam]

    def test_explicit_none_means_the_whole_thread(self) -> None:
        """Passing None as the message is the same as omitting it."""
        memory = InMemoryConversationMemory()
        emma = _detection("Emma")
        memory.remember("t1", "m1", [emma])
        assert memory.get_detections("t1", None) == [emma]

    def test_unknown_thread_has_no_detections(self) -> None:
        """A thread never written to yields an empty union."""
        assert InMemoryConversationMemory().get_detections("never") == []


class TestThreadIsolation:
    def test_threads_do_not_leak_into_each_other(self) -> None:
        """Detections in one thread never appear in another."""
        memory = InMemoryConversationMemory()
        emma = _detection("Emma")
        liam = _detection("Liam")
        memory.remember("t1", "m1", [emma])
        memory.remember("t2", "m1", [liam])
        assert memory.get_detections("t1") == [emma]
        assert memory.get_detections("t2", "m1") == [liam]


class TestForget:
    def test_forget_purges_a_thread(self) -> None:
        """Forgetting a thread drops its detections and its message cache."""
        memory = InMemoryConversationMemory()
        memory.remember("t1", "m1", [_detection("Emma")])
        memory.forget("t1")
        assert memory.get_detections("t1") == []
        assert memory.get_detections("t1", "m1") is None

    def test_forget_reports_what_it_erased(self) -> None:
        """Forgetting reports how many messages and detections were dropped."""
        memory = InMemoryConversationMemory()
        memory.remember("t1", "m1", [_detection("Emma"), _detection("Liam")])
        memory.remember("t1", "m2", [_detection("Noah")])
        assert memory.forget("t1") == Forgotten(messages=2, detections=3)

    def test_forget_unknown_thread_reports_nothing_erased(self) -> None:
        """Forgetting a thread never written reports zero and raises nothing."""
        assert InMemoryConversationMemory().forget("never") == Forgotten(0, 0)

    def test_forget_leaves_other_threads_intact(self) -> None:
        """Forgetting one thread does not touch another."""
        memory = InMemoryConversationMemory()
        liam = _detection("Liam")
        memory.remember("t1", "m1", [_detection("Emma")])
        memory.remember("t2", "m1", [liam])
        memory.forget("t1")
        assert memory.get_detections("t2") == [liam]


class TestEncapsulation:
    def test_returned_union_is_a_copy(self) -> None:
        """Mutating the returned union does not corrupt the stored detections."""
        memory = InMemoryConversationMemory()
        emma = _detection("Emma")
        memory.remember("t1", "m1", [emma])
        memory.get_detections("t1").append(_detection("Liam"))
        assert memory.get_detections("t1") == [emma]

    def test_remember_copies_its_input(self) -> None:
        """Mutating the list passed to remember does not change the store."""
        memory = InMemoryConversationMemory()
        emma = _detection("Emma")
        given = [emma]
        memory.remember("t1", "m1", given)
        given.append(_detection("Liam"))
        assert memory.get_detections("t1", "m1") == [emma]
