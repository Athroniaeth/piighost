"""LangChain middleware for transparent PII anonymization.

Needs the langchain optional dependency (pip install piighost[middleware]), so
its module is imported lazily: reaching for a symbol without the extra raises a
helpful ImportError, while importing this package never pulls langchain in.
"""

from piighost.integrations.middleware.strategy import (
    AssistantEntityStrategy,
    InventedPlaceholderStrategy,
    ToolCallStrategy,
)

__all__ = [
    "AssistantEntityStrategy",
    "InventedPlaceholderStrategy",
    "PIIAnonymizationMiddleware",
    "ToolCallStrategy",
]


def __getattr__(name: str) -> object:
    """Import the middleware on demand so its optional dependency stays optional."""
    if name == "PIIAnonymizationMiddleware":
        from piighost.integrations.middleware.langchain import (
            PIIAnonymizationMiddleware,
        )

        return PIIAnonymizationMiddleware

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
