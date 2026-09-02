"""Redis conversation memory backend (optional dependency: redis).

This module needs the redis package. It is guarded so that importing it without
the dependency raises an ImportError pointing at the extra to install. The core
conversation_memory package never imports it eagerly.

Layout, per thread, with the message hashed into the key and the value
optionally encrypted, so a secure store leak reveals neither the message nor
the PII:

  {namespace}:{thread_id}:msg:{hash}  -> [encrypt(]json({role, detections})[)]
  {namespace}:{thread_id}:index       -> [hash, ...] in first-seen order

The thread_id stays clear as a key namespace so a thread can be enumerated and
forgotten; the ordered index gives first-seen order that a key scan would not.
Crypto is optional: pass both a hasher and a cipher to store securely, or
neither to store in clear (a PIIGhostSecurityWarning is emitted). Passing
exactly one is a misuse and raises ValueError.
"""

import hashlib
import importlib.util
import json

from piighost.conversation_memory.base import Forgotten, MessageRole, warn_plaintext
from piighost.crypto.cipher.base import AnyCipher
from piighost.crypto.hasher.base import AnyHasher
from piighost.models import Detection

if importlib.util.find_spec("redis") is None:
    raise ImportError(
        "RedisConversationMemory requires the redis package. "
        "Install it with: pip install piighost[redis]"
    )

from redis.asyncio import Redis
from redis.exceptions import WatchError

_DEFAULT_NAMESPACE = "piighost"
"""Default key prefix isolating this library's keys in a shared Redis."""


def _dumps(role: MessageRole, detections: list[Detection]) -> bytes:
    """Serialize a message's role and detections to JSON bytes for storage."""
    payload = {
        "role": role.value,
        "detections": [detection.to_dict() for detection in detections],
    }
    return json.dumps(payload).encode()


def _as_bytes(value: bytes | str) -> bytes:
    """Coerce a Redis string reply to bytes, which is what was stored."""
    return value if isinstance(value, bytes) else value.encode()


def _loads(data: bytes) -> tuple[MessageRole, list[Detection]]:
    """Rebuild a message's role and detections from the bytes written by _dumps."""
    payload = json.loads(data)
    role = MessageRole(payload["role"])
    detections = [Detection.from_dict(item) for item in payload["detections"]]
    return role, detections


class RedisConversationMemory:
    """Persist each thread's message detections in Redis, optionally secured.

    Pass both a hasher and a cipher to hash keys and encrypt values, so a
    Redis leak exposes neither the message nor the PII. Pass neither to store
    in clear (a PIIGhostSecurityWarning is emitted at construction). Passing
    exactly one is a misuse and raises ValueError. An optional TTL expires
    every written entry.

    Attributes:
        namespace: The key prefix isolating this application's keys.
    """

    def __init__(
        self,
        client: Redis,
        hasher: AnyHasher | None = None,
        cipher: AnyCipher | None = None,
        namespace: str = _DEFAULT_NAMESPACE,
        ttl: int | None = None,
    ) -> None:
        """Store the client, the optional crypto, and the namespace and TTL.

        A hasher keys each message and a cipher encrypts each value; pass both to
        store securely, or neither to store in clear. Passing exactly one is a
        misuse. Redis is a networked store, so a plaintext backend warns.
        """
        if (hasher is None) != (cipher is None):
            raise ValueError("Provide both a hasher and a cipher, or neither")
        self._client = client
        self._hasher = hasher
        self._cipher = cipher
        self.namespace = namespace
        self._ttl = ttl
        if hasher is None:
            warn_plaintext("RedisConversationMemory")

    def _index_key(self, thread_id: str) -> str:
        """Return the key of a thread's first-seen order index."""
        return f"{self.namespace}:{thread_id}:index"

    def _message_key(self, thread_id: str, digest_message: str) -> str:
        """Return the key of one message's stored detections."""
        return f"{self.namespace}:{thread_id}:msg:{digest_message}"

    def _digest(self, message: str) -> str:
        """Key a message: the security hasher if set, else a plain SHA-256."""
        if self._hasher is not None:
            return self._hasher.hash(message)
        return hashlib.sha256(message.encode()).hexdigest()

    def _encrypt(self, data: bytes) -> bytes:
        """Encrypt a value if a cipher is set, else pass it through in clear."""
        return self._cipher.encrypt(data) if self._cipher is not None else data

    def _decrypt(self, data: bytes) -> bytes:
        """Decrypt a value if a cipher is set, else pass it through in clear."""
        return self._cipher.decrypt(data) if self._cipher is not None else data

    async def remember(
        self,
        thread_id: str,
        message: str,
        detections: list[Detection],
        role: MessageRole = MessageRole.USER,
    ) -> None:
        """Cache the detections found in a message, replacing any prior entry.

        The write is atomic under a WATCH on the message key, so the digest is
        appended to the index only when the message is new, and two concurrent
        first writes of the same message cannot both append it. A concurrent
        change to the key retries the transaction.
        """
        digest_message = self._digest(message)
        key = self._message_key(thread_id, digest_message)
        index_key = self._index_key(thread_id)
        blob = self._encrypt(_dumps(role, detections))

        while True:
            async with self._client.pipeline(transaction=True) as pipe:
                try:
                    await pipe.watch(key)
                    is_new = not await pipe.exists(key)
                    pipe.multi()
                    pipe.set(key, blob, ex=self._ttl)
                    if is_new:
                        pipe.rpush(index_key, digest_message)
                        if self._ttl is not None:
                            pipe.expire(index_key, self._ttl)
                    await pipe.execute()
                    return
                except WatchError:
                    continue

    async def get_detections(
        self,
        thread_id: str,
        message: str | None = None,
    ) -> list[Detection] | None:
        """Return a thread's detections, for one message or the whole thread."""
        if message is not None:
            digest_message = self._digest(message)
            key = self._message_key(thread_id, digest_message)
            blob = await self._client.get(key)
            if blob is None:
                return None
            _, detections = _loads(self._decrypt(_as_bytes(blob)))
            return detections

        return [
            detection
            for _, _, message_detections in await self._read_all(thread_id)
            for detection in message_detections
        ]

    async def get_provenance(self, thread_id: str) -> dict[str, MessageRole]:
        """Return the first-occurrence role of every value in the thread."""
        provenance: dict[str, MessageRole] = {}

        for _, role, detections in await self._read_all(thread_id):
            for detection in detections:
                provenance.setdefault(detection.text.casefold(), role)

        return provenance

    async def forget(self, thread_id: str) -> Forgotten:
        """Erase a thread and report how many messages and detections dropped."""
        records = await self._read_all(thread_id)
        messages = len(records)
        detections = sum(len(loaded) for _, _, loaded in records)

        keys = [self._index_key(thread_id)]
        keys.extend(self._message_key(thread_id, digest) for digest, _, _ in records)
        await self._client.delete(*keys)
        return Forgotten(messages=messages, detections=detections)

    async def _read_all(
        self, thread_id: str
    ) -> list[tuple[str, MessageRole, list[Detection]]]:
        """Read every present message of a thread in one MGET, in first-seen order.

        The index digests are deduplicated, so a digest appended twice by a race
        is read once, and a digest whose message key has expired is dropped from
        the index opportunistically, so the index does not grow without bound.
        """
        digests = list(dict.fromkeys(await self._digests(thread_id)))
        if not digests:
            return []

        keys = [self._message_key(thread_id, digest) for digest in digests]
        blobs = await self._client.mget(keys)

        records: list[tuple[str, MessageRole, list[Detection]]] = []
        stale: list[str] = []
        for digest, blob in zip(digests, blobs, strict=True):
            if blob is None:
                stale.append(digest)
                continue
            role, detections = _loads(self._decrypt(_as_bytes(blob)))
            records.append((digest, role, detections))

        for digest in stale:
            await self._client.lrem(self._index_key(thread_id), 0, digest)

        return records

    async def _digests(self, thread_id: str) -> list[str]:
        """Return a thread's message hashes in first-seen order."""
        digests = await self._client.lrange(self._index_key(thread_id), 0, -1)
        return [d.decode() if isinstance(d, bytes) else d for d in digests]
