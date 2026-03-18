"""Strategies for generating placeholder replacement strings."""

from collections import defaultdict
from typing import Protocol

from maskara.anonymizer.models import Placeholder


class PlaceholderFactory(Protocol):
    """Interface for creating placeholder tags.

    Each call must return a *unique* replacement string for a given
    ``(original, label)`` pair, and return the *same* string if the
    same pair is requested again within the same pass.
    """

    def get_or_create(self, original: str, label: str) -> Placeholder:
        """Return an existing placeholder or create a new one.

        Args:
            original: The sensitive text fragment.
            label: The entity type (e.g. ``"PERSON"``).

        Returns:
            A ``Placeholder`` whose ``replacement`` is unique for this
            ``(original, label)`` pair.
        """
        ...  # pragma: no cover

    def reset(self) -> None:
        """Clear internal state for a fresh anonymization pass."""
        ...  # pragma: no cover


class CounterPlaceholderFactory:
    """Generate tags like ``<<PERSON_1>>``, ``<<LOCATION_2>>``, etc.

    The factory maintains per-label counters so that each distinct
    original text gets a sequential index.  Calling ``reset`` clears
    all counters.

    Args:
        template: A format string with ``{label}`` and ``{index}``
            placeholders.  Defaults to ``"<<{label}_{index}>>"`` .

    Example:
        >>> factory = CounterPlaceholderFactory()
        >>> factory.get_or_create("Patrick", "PERSON").replacement
        '<<PERSON_1>>'
        >>> factory.get_or_create("Marie", "PERSON").replacement
        '<<PERSON_2>>'
        >>> factory.get_or_create("Patrick", "PERSON").replacement
        '<<PERSON_1>>'
    """

    def __init__(self, template: str = "<<{label}_{index}>>") -> None:
        self._template = template
        self._counters: dict[str, int] = defaultdict(int)
        self._cache: dict[tuple[str, str], Placeholder] = {}

    def get_or_create(self, original: str, label: str) -> Placeholder:
        """Return a cached placeholder or mint a new one.

        Args:
            original: The sensitive text.
            label: The entity type.

        Returns:
            A ``Placeholder`` with a deterministic replacement tag.
        """
        key = (original, label)
        if key in self._cache:
            return self._cache[key]

        self._counters[label] += 1
        replacement = self._template.format(
            label=label,
            index=self._counters[label],
        )
        placeholder = Placeholder(
            original=original,
            label=label,
            replacement=replacement,
        )
        self._cache[key] = placeholder
        return placeholder

    def reset(self) -> None:
        """Clear counters and cache for a new anonymization pass."""
        self._counters.clear()
        self._cache.clear()
