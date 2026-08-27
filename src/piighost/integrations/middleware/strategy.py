"""Deprecated alias for piighost.integrations.langchain.strategy.

Kept so existing imports keep working; importing the parent package emits the
DeprecationWarning. Prefer piighost.integrations.langchain.strategy.
"""

from typing import Any

from piighost.integrations.langchain.strategy import (
    EntityCreateByAssistantStrategy,
    InventedPlaceholderStrategy,
    ToolCallStrategy,
)

__all__ = [
    "EntityCreateByAssistantStrategy",
    "InventedPlaceholderStrategy",
    "ToolCallStrategy",
]


def __getattr__(name: str) -> Any:
    """Serve the deprecated AssistantEntityStrategy alias through langchain.strategy."""
    if name == "AssistantEntityStrategy":
        from piighost.integrations.langchain.strategy import AssistantEntityStrategy

        return AssistantEntityStrategy

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
