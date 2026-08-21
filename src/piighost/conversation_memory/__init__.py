"""Conversation memory: persist the detections found in each thread's messages.

base.py holds the abstractions, the AnyConversationMemory port and the Forgotten
erase result; concrete backends live in sibling modules. InMemoryConversationMemory
is always available. RedisConversationMemory needs the redis optional dependency,
so it is imported lazily: reaching for it without the extra raises a helpful
ImportError, while importing this package never pulls redis in.
"""

from typing import Any

from piighost.conversation_memory.base import (
    AnyConversationMemory,
    Forgotten,
    MessageRole,
)
from piighost.conversation_memory.memory import InMemoryConversationMemory

__all__ = [
    "AnyConversationMemory",
    "Forgotten",
    "InMemoryConversationMemory",
    "MessageRole",
    "RedisConversationMemory",
    "SqlAlchemyConversationMemory",
]


def __getattr__(name: str) -> Any:
    """Import the optional backends on demand to keep their extras optional."""
    if name == "RedisConversationMemory":
        from piighost.conversation_memory.redis_backend import RedisConversationMemory

        return RedisConversationMemory

    if name == "SqlAlchemyConversationMemory":
        from piighost.conversation_memory.sqlalchemy_backend import (
            SqlAlchemyConversationMemory,
        )

        return SqlAlchemyConversationMemory

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
