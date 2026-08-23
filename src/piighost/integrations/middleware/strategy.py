"""Deprecated alias for piighost.integrations.langchain.strategy.

Kept so existing imports keep working; importing the parent package emits the
DeprecationWarning. Prefer piighost.integrations.langchain.strategy.
"""

from piighost.integrations.langchain.strategy import (
    AssistantEntityStrategy,
    InventedPlaceholderStrategy,
    ToolCallStrategy,
)

__all__ = [
    "AssistantEntityStrategy",
    "InventedPlaceholderStrategy",
    "ToolCallStrategy",
]
