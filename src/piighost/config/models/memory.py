"""Conversation memory configuration models, discriminated on type."""

from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.config.models.cipher import CipherConfig
from piighost.config.models.common import _ComponentConfig
from piighost.config.models.hasher import HasherConfig
from piighost.conversation_memory.base import AnyConversationMemory


class InMemoryConfig(_ComponentConfig):
    """Config for the in-memory conversation memory, a process-local store."""

    type: Literal["in_memory"]

    def build(self) -> AnyConversationMemory:
        """Build an InMemoryConversationMemory."""
        from piighost.conversation_memory import InMemoryConversationMemory

        return InMemoryConversationMemory()


class RedisMemoryConfig(_ComponentConfig):
    """Config for the Redis conversation memory, persistent and multi-worker.

    Attributes:
        url: The Redis connection URL the client is built from.
        namespace: The key prefix isolating this library's keys in Redis.
        ttl: The seconds a stored message lives, or None to keep it until eviction.
        hasher: The hasher keying each message into its storage key.
        cipher: The cipher encrypting each stored value.
    """

    type: Literal["redis"]
    url: str
    namespace: str = "piighost"
    ttl: int | None = Field(default=None, ge=1)
    hasher: HasherConfig
    cipher: CipherConfig

    def build(self) -> AnyConversationMemory:
        """Build a RedisConversationMemory over a client built from the URL."""
        from redis.asyncio import Redis

        from piighost.conversation_memory import RedisConversationMemory

        client = Redis.from_url(self.url)
        return RedisConversationMemory(
            client,
            self.hasher.build(),
            self.cipher.build(),
            namespace=self.namespace,
            ttl=self.ttl,
        )


MemoryConfig = Annotated[
    InMemoryConfig | RedisMemoryConfig,
    Discriminator("type"),
]
