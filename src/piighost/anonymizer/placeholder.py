"""Strategies for generating placeholder replacement strings."""

import hashlib
from abc import ABC
from collections import defaultdict
from typing import Protocol

from piighost.anonymizer.models import Placeholder


class PlaceholderFactory(Protocol):
    """Interface for creating placeholder tags.

    Each call must return a replacement string for a given
    ``(original, label)`` pair, and return the *same* string if the
    same pair is requested again within the same pass.

    Not all factories are reversible.  Factories that produce unique,
    distinguishable tags should inherit from
    ``ReversiblePlaceholderFactory``.
    """

    def get_or_create(self, original: str, label: str) -> Placeholder:
        """Return an existing placeholder or create a new one.

        Args:
            original: The sensitive text fragment.
            label: The entity type (e.g. ``"PERSON"``).

        Returns:
            A ``Placeholder`` with the replacement tag.
        """
        ...  # pragma: no cover

    def reset(self) -> None:
        """Clear internal state for a fresh anonymization pass."""
        ...  # pragma: no cover


class ReversiblePlaceholderFactory(ABC):
    """Base class for factories that support deanonymization.

    Factories inheriting from this class produce *unique* replacement
    tags for each ``(original, label)`` pair, making it possible to map
    a tag back to its original value.

    Use ``isinstance(factory, ReversiblePlaceholderFactory)`` to check
    at runtime whether deanonymization is safe.
    """


class CounterPlaceholderFactory(ReversiblePlaceholderFactory):
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


class HashPlaceholderFactory(ReversiblePlaceholderFactory):
    """Generate hash-based placeholders, e.g. ``<PERSON:a1b2c3d4>``.

    Uses a SHA-256 digest of the original text (truncated to
    ``digest_length`` hex characters) to produce a deterministic,
    opaque tag identical to the strategy used by LangChain's
    built-in PII redaction middleware.

    The same ``(original, label)`` pair always produces the same tag,
    regardless of the order in which entities are encountered.

    Args:
        digest_length: Number of hex characters to keep from the
            SHA-256 digest.  Defaults to ``8``.
        template: Format string with ``{label}`` and ``{digest}``
            placeholders.  Defaults to ``"<{label}:{digest}>"``.

    Example:
        >>> factory = HashPlaceholderFactory()
        >>> p = factory.get_or_create("Patrick", "PERSON")
        >>> p.replacement
        '<PERSON:3b4c5d6e>'
        >>> factory.get_or_create("Patrick", "PERSON") is p
        True
    """

    def __init__(
        self,
        digest_length: int = 8,
        template: str = "<{label}:{digest}>",
    ) -> None:
        self._digest_length = digest_length
        self._template = template
        self._cache: dict[tuple[str, str], Placeholder] = {}

    def get_or_create(self, original: str, label: str) -> Placeholder:
        """Return a cached placeholder or mint a new hash-based one.

        Args:
            original: The sensitive text fragment.
            label: The entity type (e.g. ``"PERSON"``).

        Returns:
            A ``Placeholder`` whose replacement is a deterministic
            hash tag derived from *original* and *label*.
        """
        key = (original, label)
        if key in self._cache:
            return self._cache[key]

        bytes_ = original.encode()
        hash_ = hashlib.sha256(bytes_).hexdigest()
        digest = hash_[: self._digest_length]

        replacement = self._template.format(label=label, digest=digest)
        placeholder = Placeholder(
            original=original,
            label=label,
            replacement=replacement,
        )
        self._cache[key] = placeholder
        return placeholder

    def reset(self) -> None:
        """Clear the cache for a new anonymization pass."""
        self._cache.clear()


class RedactPlaceholderFactory:
    """Replace all entities with a single opaque tag: ``[REDACTED]``.

    Every entity is mapped to the *same* replacement string regardless
    of its label or original text.  This makes deanonymization
    impossible — no information leaks about whether two occurrences
    refer to the same entity.

    This factory does **not** implement ``ReversiblePlaceholderFactory``.
    Passing it to any component that requires deanonymization (e.g.
    ``AnonymizationPipeline``) will raise
    ``IrreversibleAnonymizationError`` at runtime, and the type checker
    will flag the mismatch statically.

    Args:
        tag: The replacement string for all entities.
            Defaults to ``"[REDACTED]"``.

    Example:
        >>> factory = RedactPlaceholderFactory()
        >>> factory.get_or_create("Patrick", "PERSON").replacement
        '[REDACTED]'
        >>> factory.get_or_create("Paris", "LOCATION").replacement
        '[REDACTED]'
    """

    def __init__(self, tag: str = "[REDACTED]") -> None:
        self._tag = tag
        self._cache: dict[tuple[str, str], Placeholder] = {}

    def get_or_create(self, original: str, label: str) -> Placeholder:
        """Return a cached placeholder or create a new one.

        All placeholders share the same replacement tag.

        Args:
            original: The sensitive text fragment.
            label: The entity type.

        Returns:
            A ``Placeholder`` whose ``replacement`` is always ``self._tag``.
        """
        key = (original, label)
        if key in self._cache:
            return self._cache[key]

        placeholder = Placeholder(
            original=original,
            label=label,
            replacement=self._tag,
        )
        self._cache[key] = placeholder
        return placeholder

    def reset(self) -> None:
        """Clear the cache for a new anonymization pass."""
        self._cache.clear()
