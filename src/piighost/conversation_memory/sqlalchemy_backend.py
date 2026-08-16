"""SQLAlchemy conversation memory backend (optional dependency: sqlalchemy).

This module needs the sqlalchemy package. It is guarded so importing it without
the dependency raises an ImportError pointing at the extra to install. The core
conversation_memory package never imports it eagerly.

Layout, one row per thread message. The message is hashed into a digest and the
detections are optionally encrypted, so a store leak reveals neither the message
nor the PII when crypto is configured:

  {table}(id, thread_id, message_digest, role, detections, detection_count)

The thread_id stays clear so a thread can be enumerated and forgotten; the
autoincrement id gives first-seen order.
"""

import hashlib
import importlib.util
import json

from piighost.conversation_memory.base import Forgotten, MessageRole, warn_plaintext
from piighost.crypto.cipher.base import AnyCipher
from piighost.crypto.hasher.base import AnyHasher
from piighost.models import Detection

if importlib.util.find_spec("sqlalchemy") is None:
    raise ImportError(
        "SqlAlchemyConversationMemory requires the sqlalchemy package. "
        "Install it with: pip install piighost[sqlalchemy]"
    )

from sqlalchemy import (  # noqa: E402
    Column,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    delete,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncEngine  # noqa: E402

_DEFAULT_TABLE = "piighost_conversation_messages"
"""Default table name holding every thread's message detections."""


class SqlAlchemyConversationMemory:
    """Persist each thread's message detections in a SQL table, durably.

    A durable AnyConversationMemory backend over an injected async engine, for
    long conversations that outlive a process. The message is keyed by a digest
    and the detections are stored in one column, optionally encrypted. Crypto is
    all-or-nothing: pass both a hasher and a cipher to store securely, or neither
    to store in clear. A networked store without crypto warns at construction.

    The engine is injected and the caller owns its lifecycle. Call create_schema
    once at startup to create the table.

    Attributes:
        table_name: The name of the table this backend reads and writes.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        hasher: AnyHasher | None = None,
        cipher: AnyCipher | None = None,
        table_name: str = _DEFAULT_TABLE,
    ) -> None:
        """Store the engine and optional crypto, and define the table."""
        if (hasher is None) != (cipher is None):
            raise ValueError("Provide both a hasher and a cipher, or neither")
        self._engine = engine
        self._hasher = hasher
        self._cipher = cipher
        self.table_name = table_name
        self._metadata = MetaData()
        self._table = Table(
            table_name,
            self._metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("thread_id", String, nullable=False, index=True),
            Column("message_digest", String, nullable=False),
            Column("role", String, nullable=False),
            Column("detections", LargeBinary, nullable=False),
            Column("detection_count", Integer, nullable=False),
            UniqueConstraint("thread_id", "message_digest"),
        )
        if hasher is None and engine.dialect.name != "sqlite":
            warn_plaintext("SqlAlchemyConversationMemory")

    async def create_schema(self) -> None:
        """Create the table if it does not exist, idempotently."""
        async with self._engine.begin() as conn:
            await conn.run_sync(self._metadata.create_all)

    def _digest(self, message: str) -> str:
        """Key a message: the security hasher if set, else a plain SHA-256."""
        if self._hasher is not None:
            return self._hasher.hash(message)
        return hashlib.sha256(message.encode()).hexdigest()

    def _serialize(self, detections: list[Detection]) -> bytes:
        """Serialize detections to JSON bytes, encrypting when a cipher is set."""
        blob = json.dumps([d.to_dict() for d in detections]).encode()
        return self._cipher.encrypt(blob) if self._cipher is not None else blob

    def _deserialize(self, data: bytes) -> list[Detection]:
        """Rebuild detections from stored bytes, decrypting when a cipher is set."""
        raw = self._cipher.decrypt(data) if self._cipher is not None else data
        return [Detection.from_dict(item) for item in json.loads(raw)]

    async def remember(
        self,
        thread_id: str,
        message: str,
        detections: list[Detection],
        role: MessageRole = MessageRole.USER,
    ) -> None:
        """Cache the detections found in a message, replacing any prior entry."""
        digest = self._digest(message)
        blob = self._serialize(detections)
        table = self._table
        async with self._engine.begin() as conn:
            found = (
                await conn.execute(
                    select(table.c.id).where(
                        table.c.thread_id == thread_id,
                        table.c.message_digest == digest,
                    )
                )
            ).first()
            values = {
                "role": role.value,
                "detections": blob,
                "detection_count": len(detections),
            }
            if found is None:
                await conn.execute(
                    insert(table).values(
                        thread_id=thread_id,
                        message_digest=digest,
                        **values,
                    )
                )
            else:
                await conn.execute(
                    update(table).where(table.c.id == found.id).values(**values)
                )

    async def get_detections(
        self,
        thread_id: str,
        message: str | None = None,
    ) -> list[Detection] | None:
        """Return a thread's detections, for one message or the whole thread."""
        table = self._table
        if message is not None:
            digest = self._digest(message)
            async with self._engine.connect() as conn:
                row = (
                    await conn.execute(
                        select(table.c.detections).where(
                            table.c.thread_id == thread_id,
                            table.c.message_digest == digest,
                        )
                    )
                ).first()
            if row is None:
                return None
            return self._deserialize(row.detections)

        async with self._engine.connect() as conn:
            rows = (
                await conn.execute(
                    select(table.c.detections)
                    .where(table.c.thread_id == thread_id)
                    .order_by(table.c.id)
                )
            ).all()
        detections: list[Detection] = []
        for row in rows:
            detections.extend(self._deserialize(row.detections))
        return detections

    async def get_provenance(self, thread_id: str) -> dict[str, MessageRole]:
        """Return the first-occurrence role of every value in the thread."""
        table = self._table
        async with self._engine.connect() as conn:
            rows = (
                await conn.execute(
                    select(table.c.role, table.c.detections)
                    .where(table.c.thread_id == thread_id)
                    .order_by(table.c.id)
                )
            ).all()
        provenance: dict[str, MessageRole] = {}
        for row in rows:
            role = MessageRole(row.role)
            for detection in self._deserialize(row.detections):
                provenance.setdefault(detection.text.casefold(), role)
        return provenance

    async def forget(self, thread_id: str) -> Forgotten:
        """Erase a thread and report how many messages and detections dropped."""
        table = self._table
        async with self._engine.begin() as conn:
            totals = (
                await conn.execute(
                    select(
                        func.count(),
                        func.coalesce(func.sum(table.c.detection_count), 0),
                    ).where(table.c.thread_id == thread_id)
                )
            ).one()
            await conn.execute(delete(table).where(table.c.thread_id == thread_id))
        return Forgotten(messages=int(totals[0]), detections=int(totals[1]))
