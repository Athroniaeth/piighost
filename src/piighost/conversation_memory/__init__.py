"""Conversation memory: persist the detections found in each thread's messages.

base.py holds the abstractions, the AnyConversationMemory port and the Forgotten
erase result; concrete backends live in sibling modules. InMemoryConversationMemory
is always available. RedisConversationMemory needs the redis optional dependency,
so it is imported lazily: reaching for it without the extra raises a helpful
ImportError, while importing this package never pulls redis in.
"""

from piighost.conversation_memory.base import AnyConversationMemory, Forgotten
from piighost.conversation_memory.memory import InMemoryConversationMemory

__all__ = [
    "AnyConversationMemory",
    "Forgotten",
    "InMemoryConversationMemory",
    "RedisConversationMemory",
]


def __getattr__(name: str) -> object:
    """Import RedisConversationMemory on demand to keep redis optional."""
    if name == "RedisConversationMemory":
        from piighost.conversation_memory.redis_backend import RedisConversationMemory

        return RedisConversationMemory

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
