"""Deprecated alias for piighost.integrations.langchain.

The LangChain middleware moved to piighost.integrations.langchain in 1.4.0. This
module re-exports the same names so existing imports keep working, but importing
it emits a DeprecationWarning. It will be removed in a future major release.
"""

import warnings
from typing import Any

from piighost.integrations.langchain.strategy import (
    EntityCreateByAssistantStrategy,
    InventedPlaceholderStrategy,
    ToolCallStrategy,
)

warnings.warn(
    "piighost.integrations.middleware is deprecated; import from "
    "piighost.integrations.langchain instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "EntityCreateByAssistantStrategy",
    "InventedPlaceholderStrategy",
    "PIIAnonymizationMiddleware",
    "ToolCallStrategy",
]


def __getattr__(name: str) -> Any:
    """Import the middleware on demand, and serve the deprecated strategy alias."""
    if name == "PIIAnonymizationMiddleware":
        from piighost.integrations.langchain.middleware import (
            PIIAnonymizationMiddleware,
        )

        return PIIAnonymizationMiddleware

    if name == "AssistantEntityStrategy":
        from piighost.integrations.langchain.strategy import AssistantEntityStrategy

        return AssistantEntityStrategy

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
