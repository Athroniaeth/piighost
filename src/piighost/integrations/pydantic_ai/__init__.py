"""Pydantic AI capability for transparent PII de-identification.

Needs the pydantic-ai optional dependency (pip install piighost[pydantic-ai]), so
its module is imported lazily: reaching for pii_hooks without the extra raises a
helpful ImportError, while importing this package never pulls pydantic-ai in.
"""

from typing import Any

__all__ = ["pii_hooks"]


def __getattr__(name: str) -> Any:
    """Import pii_hooks on demand so its optional dependency stays optional."""
    if name == "pii_hooks":
        from piighost.integrations.pydantic_ai.hooks import pii_hooks

        return pii_hooks

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
