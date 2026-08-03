"""Redis conversation memory backend (optional dependency: redis).

This module needs the redis package. It is guarded so that importing it without
the dependency raises an ImportError pointing at the extra to install. The core
conversation_memory package never imports it eagerly.

Layout, per thread, with the message hashed into the key and the value
encrypted, so a store leak reveals neither the message nor the PII:

  {namespace}:{thread_id}:msg:{hash}  -> encrypt(json(detections))
  {namespace}:{thread_id}:index       -> [hash, ...] in first-seen order

The thread_id stays clear as a key namespace so a thread can be enumerated and
forgotten; the ordered index gives first-seen order that a key scan would not.
"""

import importlib.util
import json

from piighost.cipher.base import AnyCipher
from piighost.conversation_memory.base import Forgotten
from piighost.hasher.base import AnyHasher
from piighost.models import Detection

if importlib.util.find_spec("redis") is None:
    raise ImportError(
        "RedisConversationMemory requires the redis package. "
        "Install it with: pip install piighost[redis]"
    )

from redis.asyncio import Redis  # noqa: E402

_DEFAULT_NAMESPACE = "piighost"


def _dumps(detections: list[Detection]) -> bytes:
    """Serialize detections to JSON bytes for encrypted storage."""
    return json.dumps([detection.to_dict() for detection in detections]).encode()


def _as_bytes(value: bytes | str) -> bytes:
    """Coerce a Redis string reply to bytes, which is what was stored."""
    return value if isinstance(value, bytes) else value.encode()


def _loads(data: bytes) -> list[Detection]:
    """Rebuild detections from the JSON bytes written by _dumps."""
    return [Detection.from_dict(item) for item in json.loads(data)]


class RedisConversationMemory:
    """Persist each thread's message detections in Redis, hashed and encrypted.

    The message is hashed into the key by the injected hasher, and the
    detections are encrypted by the injected cipher, so a leak of Redis exposes
    neither the message nor the PII. Both are required: the backend exists to
    persist securely. An optional TTL expires every written entry.

    Attributes:
        namespace: The key prefix isolating this application's keys.
    """

    def __init__(
        self,
        client: Redis,
        hasher: AnyHasher,
        cipher: AnyCipher,
        namespace: str = _DEFAULT_NAMESPACE,
        ttl: int | None = None,
    ) -> None:
        """Store the client, the hasher and cipher, and the namespace and TTL."""
        self._client = client
        self._hasher = hasher
        self._cipher = cipher
        self.namespace = namespace
        self._ttl = ttl

    def _index_key(self, thread_id: str) -> str:
        """Return the key of a thread's first-seen order index."""
        return f"{self.namespace}:{thread_id}:index"

    def _message_key(self, thread_id: str, digest_message: str) -> str:
        """Return the key of one message's stored detections."""
        return f"{self.namespace}:{thread_id}:msg:{digest_message}"

    async def remember(
        self,
        thread_id: str,
        message: str,
        detections: list[Detection],
    ) -> None:
        """Cache the detections found in a message, replacing any prior entry."""
        digest_message = self._hasher.hash(message)
        key = self._message_key(thread_id, digest_message)
        json_detections = _dumps(detections)

        blob = self._cipher.encrypt(json_detections)
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
            digest_message = self._hasher.hash(message)
            key = self._message_key(thread_id, digest_message)
            blob = await self._client.get(key)
            if blob is None:
                return None
            json_detections = self._cipher.decrypt(_as_bytes(blob))
            return _loads(json_detections)

        detections: list[Detection] = []
        for digest_message in await self._digests(thread_id):
            key = self._message_key(thread_id, digest_message)
            blob = await self._client.get(key)
            if blob is not None:
                json_detections = self._cipher.decrypt(_as_bytes(blob))
                detections.extend(_loads(json_detections))

        return detections

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
                loaded = _loads(self._cipher.decrypt(_as_bytes(blob)))
                detections += len(loaded)
            keys.append(key)

        await self._client.delete(*keys)
        return Forgotten(messages=messages, detections=detections)

    async def _digests(self, thread_id: str) -> list[str]:
        """Return a thread's message hashes in first-seen order."""
        digests = await self._client.lrange(self._index_key(thread_id), 0, -1)
        return [d.decode() if isinstance(d, bytes) else d for d in digests]
