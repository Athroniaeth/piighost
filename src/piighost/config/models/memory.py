"""Conversation memory configuration model."""

from typing import Literal

from piighost.config.models.common import _ComponentConfig
from piighost.conversation_memory.base import AnyConversationMemory


class InMemoryConfig(_ComponentConfig):
    """Config for the in-memory conversation memory, a process-local store."""

    type: Literal["in_memory"]

    def build(self) -> AnyConversationMemory:
        """Build an InMemoryConversationMemory."""
        from piighost.conversation_memory import InMemoryConversationMemory

        return InMemoryConversationMemory()


MemoryConfig = InMemoryConfig
"""The conversation memory configuration.

A plain alias while one backend exists; it becomes a discriminated union when
the redis backend lands.
"""
