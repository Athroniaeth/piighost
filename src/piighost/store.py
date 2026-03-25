"""Async key-value store for anonymization results.

The ``PlaceholderStore`` protocol defines the persistence interface used by
``AnonymizationPipeline`` to cache ``AnonymizationResult`` objects across
requests or sessions.

Implementations may use Redis, a database, or the bundled
``InMemoryPlaceholderStore`` for tests and single-process use.
"""

import hashlib
from typing import Protocol

from piighost.anonymizer.models import AnonymizationResult


class PlaceholderStore(Protocol):
    """Async key-value store for ``AnonymizationResult`` objects.

    Implementations may use Redis, an in-memory dict, or any other
    backend.  The pipeline depends only on this protocol.
    """

    async def get(self, key: str) -> AnonymizationResult | None:
        """Retrieve a stored result by key.

        Args:
            key: A deterministic hash of a text.

        Returns:
            The stored result, or *None* if the key is unknown.
        """
        ...  # pragma: no cover

    async def set(self, key: str, result: AnonymizationResult) -> None:
        """Persist an anonymization result.

        Args:
            key: A deterministic hash of a text.
            result: The result to store.
        """
        ...  # pragma: no cover


class InMemoryPlaceholderStore:
    """Simple in-memory store – suitable for tests and single-process use."""

    def __init__(self) -> None:
        self._data: dict[str, AnonymizationResult] = {}

    async def get(self, key: str) -> AnonymizationResult | None:
        """Return the stored result or *None*."""
        return self._data.get(key)

    async def set(self, key: str, result: AnonymizationResult) -> None:
        """Store an anonymization result."""
        self._data[key] = result


def text_hash(text: str) -> str:
    """Return a deterministic SHA-256 hex digest for *text*.

    Args:
        text: The source string.

    Returns:
        A hex digest string.
    """
    return hashlib.sha256(text.encode()).hexdigest()
