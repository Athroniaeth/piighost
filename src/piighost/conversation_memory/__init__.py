"""Conversation memory: persist the detections found in each thread's messages.

base.py holds the abstractions, the AnyConversationMemory port and the Forgotten
erase result; concrete backends live in sibling modules.
"""

from piighost.conversation_memory.base import AnyConversationMemory, Forgotten
from piighost.conversation_memory.memory import InMemoryConversationMemory

__all__ = ["AnyConversationMemory", "Forgotten", "InMemoryConversationMemory"]
