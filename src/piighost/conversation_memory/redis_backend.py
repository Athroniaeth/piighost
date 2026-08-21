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

from piighost.crypto.cipher.base import AnyCipher
from piighost.conversation_memory.base import Forgotten, MessageRole, warn_plaintext
from piighost.crypto.hasher.base import AnyHasher
from piighost.models import Detection

if importlib.util.find_spec("redis") is None:
    raise ImportError(
        "RedisConversationMemory requires the redis package. "
        "Install it with: pip install piighost[redis]"
    )

from redis.asyncio import Redis  # noqa: E402

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
        """Cache the detections found in a message, replacing any prior entry."""
        digest_message = self._digest(message)
        key = self._message_key(thread_id, digest_message)
        json_detections = _dumps(role, detections)

        blob = self._encrypt(json_detections)
        is_new = not await self._client.exists(key)

        await self._client.set(key, blob, ex=self._ttl)

        if is_new:
            index_key = self._index_key(thread_id)
            await self._client.rpush(index_key, digest_message)
            if self._ttl is not None:
                await self._client.expire(index_key, self._ttl)

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
            ciphertext = _as_bytes(blob)
            json_detections = self._decrypt(ciphertext)
            _, detections = _loads(json_detections)
            return detections

        detections: list[Detection] = []
        for digest_message in await self._digests(thread_id):
            key = self._message_key(thread_id, digest_message)
            blob = await self._client.get(key)
            if blob is not None:
                ciphertext = _as_bytes(blob)
                json_detections = self._decrypt(ciphertext)
                _, message_detections = _loads(json_detections)
                detections.extend(message_detections)

        return detections

    async def get_provenance(self, thread_id: str) -> dict[str, MessageRole]:
        """Return the first-occurrence role of every value in the thread."""
        provenance: dict[str, MessageRole] = {}

        for digest_message in await self._digests(thread_id):
            key = self._message_key(thread_id, digest_message)
            blob = await self._client.get(key)
            if blob is None:
                continue
            ciphertext = _as_bytes(blob)
            json_detections = self._decrypt(ciphertext)
            role, detections = _loads(json_detections)
            for detection in detections:
                provenance.setdefault(detection.text.casefold(), role)

        return provenance

    async def forget(self, thread_id: str) -> Forgotten:
        """Erase a thread and report how many messages and detections dropped."""
        index_key = self._index_key(thread_id)
        keys = [index_key]
        messages = 0
        detections = 0

        for digest in await self._digests(thread_id):
            key = self._message_key(thread_id, digest)
            blob = await self._client.get(key)
            if blob is not None:
                messages += 1
                ciphertext = _as_bytes(blob)
                json_detections = self._decrypt(ciphertext)
                _, loaded = _loads(json_detections)
                detections += len(loaded)
            keys.append(key)

        await self._client.delete(*keys)
        return Forgotten(messages=messages, detections=detections)

    async def _digests(self, thread_id: str) -> list[str]:
        """Return a thread's message hashes in first-seen order."""
        digests = await self._client.lrange(self._index_key(thread_id), 0, -1)
        return [d.decode() if isinstance(d, bytes) else d for d in digests]
