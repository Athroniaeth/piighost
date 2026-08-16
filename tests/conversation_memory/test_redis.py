"""Tests for the Redis conversation memory backend and its dependency guard."""

import importlib
import importlib.util
import sys
from typing import Any

import pytest

from piighost.conversation_memory import Forgotten, MessageRole
from piighost.models import Detection, Span

_MODULE = "piighost.conversation_memory.redis_backend"
_AES_KEY = b"0123456789abcdef0123456789abcdef"
"""A 32-byte key, the AES-256 size."""


def _detection(text: str, label: str = "PERSON") -> Detection:
    """Build a detection for the given text and label at a dummy span."""
    return Detection(span=Span(0, len(text)), text=text, label=label, confidence=0.9)


def _make() -> tuple[Any, Any]:
    """Build a RedisConversationMemory over a fresh fake Redis client."""
    pytest.importorskip("cryptography")
    fakeredis = pytest.importorskip("fakeredis.aioredis")

    from piighost.crypto.cipher import AesGcmCipher
    from piighost.conversation_memory import RedisConversationMemory
    from piighost.crypto.hasher import Sha256Hasher

    client = fakeredis.FakeRedis()
    memory = RedisConversationMemory(
        client, Sha256Hasher("pepper"), AesGcmCipher(_AES_KEY)
    )
    return memory, client


class TestOptionalDependencyGuard:
    def test_missing_redis_explains_how_to_install(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Importing without redis points the user at piighost[redis]."""
        real_find_spec = importlib.util.find_spec

        def find_spec(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "redis":
                return None
            return real_find_spec(name, *args, **kwargs)

        monkeypatch.setattr(importlib.util, "find_spec", find_spec)
        sys.modules.pop(_MODULE, None)

        with pytest.raises(ImportError, match=r"piighost\[redis\]"):
            importlib.import_module(_MODULE)

        sys.modules.pop(_MODULE, None)


class TestConformance:
    async def test_satisfies_the_port(self) -> None:
        """RedisConversationMemory is an AnyConversationMemory."""
        from piighost.conversation_memory import AnyConversationMemory

        memory, _ = _make()
        assert isinstance(memory, AnyConversationMemory)


class TestGetDetections:
    async def test_round_trip_for_a_message(self) -> None:
        """A remembered message is recalled with its detections."""
        memory, _ = _make()
        emma = _detection("Emma")
        await memory.remember("t1", "I am Emma", [emma])
        assert await memory.get_detections("t1", "I am Emma") == [emma]

    async def test_unknown_message_is_a_miss(self) -> None:
        """A message never remembered returns None."""
        memory, _ = _make()
        assert await memory.get_detections("t1", "nope") is None

    async def test_clean_message_is_a_hit_with_no_detections(self) -> None:
        """A remembered message with no PII returns an empty list, not None."""
        memory, _ = _make()
        await memory.remember("t1", "hi", [])
        assert await memory.get_detections("t1", "hi") == []

    async def test_union_in_first_seen_order(self) -> None:
        """The union flattens every message's detections in first-seen order."""
        memory, _ = _make()
        emma, liam = _detection("Emma"), _detection("Liam")
        await memory.remember("t1", "m1", [emma])
        await memory.remember("t1", "m2", [liam])
        assert await memory.get_detections("t1") == [emma, liam]

    async def test_overwriting_a_message_does_not_duplicate_in_union(self) -> None:
        """Re-remembering a message replaces it without a second index entry."""
        memory, _ = _make()
        await memory.remember("t1", "m1", [_detection("Emma")])
        liam = _detection("Liam")
        await memory.remember("t1", "m1", [liam])
        assert await memory.get_detections("t1") == [liam]


class TestThreadIsolation:
    async def test_threads_do_not_leak(self) -> None:
        """Detections in one thread never appear in another."""
        memory, _ = _make()
        emma, liam = _detection("Emma"), _detection("Liam")
        await memory.remember("t1", "m1", [emma])
        await memory.remember("t2", "m1", [liam])
        assert await memory.get_detections("t1") == [emma]
        assert await memory.get_detections("t2") == [liam]


class TestForget:
    async def test_forget_purges_and_reports(self) -> None:
        """Forgetting drops a thread and reports messages and detections."""
        memory, _ = _make()
        await memory.remember("t1", "m1", [_detection("Emma"), _detection("Liam")])
        await memory.remember("t1", "m2", [_detection("Noah")])
        assert await memory.forget("t1") == Forgotten(messages=2, detections=3)
        assert await memory.get_detections("t1") == []

    async def test_forget_unknown_thread_reports_nothing(self) -> None:
        """Forgetting a thread never written reports zero and raises nothing."""
        memory, _ = _make()
        assert await memory.forget("never") == Forgotten(0, 0)

    async def test_forget_leaves_other_threads(self) -> None:
        """Forgetting one thread does not touch another."""
        memory, _ = _make()
        liam = _detection("Liam")
        await memory.remember("t1", "m1", [_detection("Emma")])
        await memory.remember("t2", "m1", [liam])
        await memory.forget("t1")
        assert await memory.get_detections("t2") == [liam]


class TestAtRestProtection:
    async def test_message_text_is_not_stored_in_any_key(self) -> None:
        """The message is hashed into the key, never stored in the clear."""
        memory, client = _make()
        await memory.remember("t1", "I am Emma", [_detection("Emma")])
        keys = [
            key.decode() if isinstance(key, bytes) else key
            for key in await client.keys("*")
        ]
        assert keys
        assert all("I am Emma" not in key for key in keys)

    async def test_detections_are_encrypted_at_rest(self) -> None:
        """The stored value is ciphertext, so the PII is not readable at rest."""
        memory, client = _make()
        await memory.remember("t1", "I am Emma", [_detection("Emma")])
        stored = b"".join(
            [await client.get(key) for key in await client.keys("*:msg:*")]
        )
        assert stored
        assert b"Emma" not in stored


class TestProvenance:
    async def test_records_first_occurrence_role(self) -> None:
        """A value keeps the role of the message that first held it."""
        memory, _ = _make()
        await memory.remember("t1", "u1", [_detection("Napoleon")], MessageRole.USER)
        await memory.remember(
            "t1", "a1", [_detection("Napoleon")], MessageRole.ASSISTANT
        )
        assert await memory.get_provenance("t1") == {"napoleon": MessageRole.USER}

    async def test_default_role_is_user(self) -> None:
        """Remembering without a role records USER provenance."""
        memory, _ = _make()
        await memory.remember("t1", "u1", [_detection("Emma")])
        assert await memory.get_provenance("t1") == {"emma": MessageRole.USER}

    async def test_unknown_thread_has_no_provenance(self) -> None:
        """A thread never written to yields an empty provenance map."""
        memory, _ = _make()
        assert await memory.get_provenance("never") == {}
