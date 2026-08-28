"""Tests for the SQLAlchemy conversation memory backend."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy")

import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from piighost.components.detector import ExactMatchDetector
from piighost.conversation_memory import (
    AnyConversationMemory,
    SqlAlchemyConversationMemory,
)
from piighost.conversation_memory.base import MessageRole
from piighost.exceptions import PIIGhostSecurityWarning

_AES_KEY = b"0123456789abcdef0123456789abcdef"
"""A 32-byte key, the AES-256 size."""


@pytest_asyncio.fixture
async def memory(tmp_path: Path) -> AsyncIterator[SqlAlchemyConversationMemory]:
    """Build a schema-created sqlite-backed memory over a temp file database."""
    url = f"sqlite+aiosqlite:///{tmp_path / 'memory.db'}"
    engine = create_async_engine(url)
    store = SqlAlchemyConversationMemory(engine)
    await store.create_schema()
    yield store
    await engine.dispose()


class TestConformance:
    def test_satisfies_the_port(self, memory: SqlAlchemyConversationMemory) -> None:
        """The backend is an AnyConversationMemory."""
        assert isinstance(memory, AnyConversationMemory)


class TestRoundTrip:
    async def test_remembers_and_returns_a_message(
        self, memory: SqlAlchemyConversationMemory
    ) -> None:
        """A remembered message's detections come back for that message."""
        detections = await ExactMatchDetector({"Emma": "PERSON"}).detect("Hi Emma")
        await memory.remember("t1", "Hi Emma", detections)
        assert await memory.get_detections("t1", "Hi Emma") == detections

    async def test_unseen_message_returns_none(
        self, memory: SqlAlchemyConversationMemory
    ) -> None:
        """A message never remembered returns None so detection runs."""
        assert await memory.get_detections("t1", "never") is None

    async def test_whole_thread_unions_in_first_seen_order(
        self, memory: SqlAlchemyConversationMemory
    ) -> None:
        """With no message, the union of every message's detections is returned."""
        first = await ExactMatchDetector({"Emma": "PERSON"}).detect("Hi Emma")
        second = await ExactMatchDetector({"Liam": "PERSON"}).detect("and Liam")
        await memory.remember("t1", "Hi Emma", first)
        await memory.remember("t1", "and Liam", second)
        assert await memory.get_detections("t1") == first + second

    async def test_clean_message_is_a_hit_with_no_detections(
        self, memory: SqlAlchemyConversationMemory
    ) -> None:
        """A remembered clean message is a hit returning an empty list, not None."""
        await memory.remember("t1", "nothing here", [])
        assert await memory.get_detections("t1", "nothing here") == []
        assert await memory.get_detections("t1", "unseen") is None

    async def test_rewriting_a_message_keeps_first_seen_order(
        self, memory: SqlAlchemyConversationMemory
    ) -> None:
        """Re-remembering a message updates it in place without reordering."""
        emma = await ExactMatchDetector({"Emma": "PERSON"}).detect("Hi Emma")
        liam = await ExactMatchDetector({"Liam": "PERSON"}).detect("and Liam")
        await memory.remember("t1", "Hi Emma", emma)
        await memory.remember("t1", "and Liam", liam)
        await memory.remember("t1", "Hi Emma", emma)  # rewrite
        assert await memory.get_detections("t1") == emma + liam


class TestProvenance:
    async def test_first_occurrence_role_wins(
        self, memory: SqlAlchemyConversationMemory
    ) -> None:
        """A value keeps the role of its earliest message."""
        detections = await ExactMatchDetector({"Emma": "PERSON"}).detect("Emma")
        await memory.remember("t1", "Emma", detections, role=MessageRole.ASSISTANT)
        await memory.remember("t1", "Emma again", detections, role=MessageRole.USER)
        assert (await memory.get_provenance("t1"))["emma"] is MessageRole.ASSISTANT


class TestForget:
    async def test_forget_reports_and_erases(
        self, memory: SqlAlchemyConversationMemory
    ) -> None:
        """Forgetting a thread erases it and reports the counts dropped."""
        detections = await ExactMatchDetector({"Emma": "PERSON"}).detect("Hi Emma")
        await memory.remember("t1", "Hi Emma", detections)
        forgotten = await memory.forget("t1")
        assert forgotten.messages == 1
        assert forgotten.detections == 1
        assert await memory.get_detections("t1") == []

    async def test_forget_unknown_thread_reports_zero(
        self, memory: SqlAlchemyConversationMemory
    ) -> None:
        """Forgetting a thread never written drops nothing."""
        forgotten = await memory.forget("ghost")
        assert forgotten.messages == 0
        assert forgotten.detections == 0


class TestCrypto:
    async def test_exactly_one_of_hasher_cipher_is_refused(
        self, tmp_path: Path
    ) -> None:
        """Providing only a hasher, or only a cipher, is a misuse."""
        from piighost.crypto.hasher import Sha256Hasher

        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'x.db'}")
        with pytest.raises(ValueError):
            SqlAlchemyConversationMemory(engine, hasher=Sha256Hasher("pepper"))
        await engine.dispose()

    async def test_encrypted_round_trip(self, tmp_path: Path) -> None:
        """With a hasher and cipher, detections still round-trip through crypto."""
        pytest.importorskip("cryptography")

        from piighost.crypto.cipher import AesGcmCipher
        from piighost.crypto.hasher import Sha256Hasher

        url = f"sqlite+aiosqlite:///{tmp_path / 'secure.db'}"
        engine = create_async_engine(url)
        hasher = Sha256Hasher("pepper")
        cipher = AesGcmCipher(_AES_KEY)
        store = SqlAlchemyConversationMemory(engine, hasher=hasher, cipher=cipher)
        await store.create_schema()
        detections = await ExactMatchDetector({"Emma": "PERSON"}).detect("Hi Emma")
        await store.remember("t1", "Hi Emma", detections)
        assert await store.get_detections("t1", "Hi Emma") == detections
        await engine.dispose()


class TestWarning:
    async def test_networked_dialect_without_crypto_warns(self) -> None:
        """A postgres engine with no crypto warns; building it does not connect."""
        engine = create_async_engine("postgresql+asyncpg://u:p@localhost/db")
        with pytest.warns(PIIGhostSecurityWarning):
            SqlAlchemyConversationMemory(engine)
        await engine.dispose()

    def test_sqlite_without_crypto_is_silent(
        self, memory: SqlAlchemyConversationMemory
    ) -> None:
        """A sqlite backend without crypto does not warn (local dev)."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("error", PIIGhostSecurityWarning)
            assert isinstance(memory, SqlAlchemyConversationMemory)
