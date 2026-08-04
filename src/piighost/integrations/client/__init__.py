"""Remote client for piighost-api.

PIIGhostClient needs the httpx optional dependency, so it is imported lazily:
reaching for it without the extra raises a helpful ImportError, while importing
this package never pulls httpx in.
"""

from typing import Any

__all__ = ["PIIGhostClient"]


def __getattr__(name: str) -> Any:
    """Import PIIGhostClient on demand so its optional dependency stays optional."""
    if name == "PIIGhostClient":
        from piighost.integrations.client.remote import PIIGhostClient

        return PIIGhostClient

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
