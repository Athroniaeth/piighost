"""Conversation memory configuration models, discriminated on type."""

from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.config.models.cipher import CipherConfig
from piighost.config.models.common import _ComponentConfig
from piighost.config.models.hasher import HasherConfig
from piighost.conversation_memory.base import AnyConversationMemory


class InMemoryConfig(_ComponentConfig):
    """Config for the in-memory conversation memory, a process-local store.

    Attributes:
        max_threads: The most threads to keep, evicting the least recently used
            beyond it, or None for no bound.
        ttl: The seconds a thread lives after its last write, expired lazily on
            the next access, or None to keep it until eviction or forget.
    """

    type: Literal["in_memory"]
    max_threads: int | None = Field(default=None, ge=1)
    ttl: float | None = Field(default=None, gt=0)

    def build(self) -> AnyConversationMemory:
        """Build an InMemoryConversationMemory with the configured bounds."""
        from piighost.conversation_memory import InMemoryConversationMemory

        return InMemoryConversationMemory(max_threads=self.max_threads, ttl=self.ttl)


class RedisMemoryConfig(_ComponentConfig):
    """Config for the Redis conversation memory, persistent and multi-worker.

    Attributes:
        url: The Redis connection URL the client is built from.
        namespace: The key prefix isolating this library's keys in Redis.
        ttl: The seconds a stored message lives, or None to keep it until eviction.
        hasher: The optional hasher keying each message into its storage key.
        cipher: The optional cipher encrypting each stored value.
    """

    type: Literal["redis"]
    url: str
    namespace: str = "piighost"
    ttl: int | None = Field(default=None, ge=1)
    hasher: HasherConfig | None = None
    cipher: CipherConfig | None = None

    def build(self) -> AnyConversationMemory:
        """Build a RedisConversationMemory over a client built from the URL."""
        from redis.asyncio import Redis

        from piighost.conversation_memory import RedisConversationMemory
        from piighost.exceptions import ConfigError

        if (self.hasher is None) != (self.cipher is None):
            raise ConfigError("Configure both a hasher and a cipher, or neither")
        client = Redis.from_url(self.url)
        hasher = self.hasher.build() if self.hasher is not None else None
        cipher = self.cipher.build() if self.cipher is not None else None
        return RedisConversationMemory(
            client,
            hasher,
            cipher,
            namespace=self.namespace,
            ttl=self.ttl,
        )


class SqlAlchemyMemoryConfig(_ComponentConfig):
    """Config for the SQLAlchemy conversation memory, durable and long-lived.

    Attributes:
        url_env: The environment variable holding the database URL, read at
            build time so the URL and its password stay out of the config file.
        table_name: The table the backend reads and writes.
        hasher: The optional hasher keying each message into its digest.
        cipher: The optional cipher encrypting each stored value.
    """

    type: Literal["sqlalchemy"]
    url_env: str = "PIIGHOST_DATABASE_URL"
    table_name: str = "piighost_conversation_messages"
    hasher: HasherConfig | None = None
    cipher: CipherConfig | None = None

    def build(self) -> AnyConversationMemory:
        """Build a SqlAlchemyConversationMemory over an engine from the URL env."""
        import os

        from sqlalchemy.ext.asyncio import create_async_engine

        from piighost.conversation_memory import SqlAlchemyConversationMemory
        from piighost.exceptions import ConfigError

        if (self.hasher is None) != (self.cipher is None):
            raise ConfigError("Configure both a hasher and a cipher, or neither")
        url = os.environ.get(self.url_env)
        if not url:
            raise ConfigError(
                f"The SQLAlchemy memory needs the {self.url_env} environment "
                f"variable holding the database URL"
            )
        engine = create_async_engine(url)
        hasher = self.hasher.build() if self.hasher is not None else None
        cipher = self.cipher.build() if self.cipher is not None else None
        return SqlAlchemyConversationMemory(
            engine,
            hasher,
            cipher,
            table_name=self.table_name,
        )


MemoryConfig = Annotated[
    InMemoryConfig | RedisMemoryConfig | SqlAlchemyMemoryConfig,
    Discriminator("type"),
]
