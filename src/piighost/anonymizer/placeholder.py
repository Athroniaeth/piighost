"""Strategies for generating placeholder replacement strings."""

import hashlib
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Literal, NoReturn

from piighost.anonymizer.models import IrreversibleAnonymizationError, Placeholder


class PlaceholderFactory(ABC):
    """Abstract base for all placeholder factories.

    A factory has **two roles**:

    1. **Naming strategy** ``create`` generates a fresh ``Placeholder``
       for a given ``(original, label)`` pair.  Override this in
       subclasses.
    2. **Self-caching convenience** ``get_or_create`` wraps ``create``
       with an internal ``(original, label) → Placeholder`` cache so
       the same pair always receives the same tag.

    Use ``create`` directly when an **external** cache (e.g.
    ``PlaceholderRegistry``) already handles deduplication.
    Use ``get_or_create`` for **standalone** usage where the factory
    manages its own cache.

    Use one of the two intermediate bases instead of subclassing
    this directly:

    * ``ReversiblePlaceholderFactory`` unique tags, deanonymization OK.
    * ``IrreversiblePlaceholderFactory`` opaque tags, no deanonymization.
    """

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], Placeholder] = {}

    def get_or_create(self, original: str, label: str) -> Placeholder:
        """Return an existing placeholder or create a new one.

        Uses an internal cache keyed by ``(original, label)``.  For
        external caching (e.g. via ``PlaceholderRegistry``), call
        ``create`` directly instead.

        Args:
            original: The sensitive text fragment.
            label: The entity type (e.g. ``"PERSON"``).

        Returns:
            A ``Placeholder`` with the replacement tag.
        """
        key = (original, label)
        if key in self._cache:
            return self._cache[key]

        placeholder = self.create(original, label)
        self._cache[key] = placeholder
        return placeholder

    @abstractmethod
    def create(self, original: str, label: str) -> Placeholder:
        """Create a fresh placeholder (pure naming strategy).

        This method always mints a **new** placeholder and should be
        called through ``get_or_create`` when deduplication is needed,
        or called directly when an external cache handles it.

        Args:
            original: The sensitive text fragment.
            label: The entity type.

        Returns:
            A fresh ``Placeholder``.
        """

    def reset(self) -> None:
        """Clear internal state for a fresh anonymization pass."""
        self._cache.clear()
        self._reset()

    def _reset(self) -> None:
        """Hook for subclass-specific reset logic. Override if needed."""

    @property
    @abstractmethod
    def reversible(self) -> bool:
        """Whether this factory supports deanonymization."""

    @abstractmethod
    def check_reversible(self) -> None:
        """Raise if the factory does not support deanonymization.

        Raises:
            IrreversibleAnonymizationError: If the factory is not
                reversible.
        """


class ReversiblePlaceholderFactory(PlaceholderFactory, ABC):
    """Base class for factories that support deanonymization.

    Factories inheriting from this class produce *unique* replacement
    tags for each ``(original, label)`` pair, making it possible to map
    a tag back to its original value.

    Use ``factory.reversible`` to check at runtime whether
    deanonymization is safe.
    """

    @property
    def reversible(self) -> Literal[True]:
        """Always ``True`` reversible factories support deanonymization."""
        return True

    def check_reversible(self) -> None:
        """No-op reversible factories always pass this check."""


class IrreversiblePlaceholderFactory(PlaceholderFactory, ABC):
    """Base class for factories that do **not** support deanonymization.

    Calling ``check_reversible`` always raises
    ``IrreversibleAnonymizationError``.
    """

    @property
    def reversible(self) -> Literal[False]:
        """Always ``False`` irreversible factories cannot deanonymize."""
        return False

    def check_reversible(self) -> NoReturn:
        """Raise ``IrreversibleAnonymizationError``."""
        msg = (
            f"{type(self).__name__} is not reversible. "
            "Deanonymization requires a ReversiblePlaceholderFactory "
            "(e.g. CounterPlaceholderFactory or HashPlaceholderFactory)."
        )
        raise IrreversibleAnonymizationError(msg)


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
        super().__init__()
        self._template = template
        self._counters: dict[str, int] = defaultdict(int)

    def create(self, original: str, label: str) -> Placeholder:
        """Mint a new counter-based placeholder.

        Args:
            original: The sensitive text.
            label: The entity type.

        Returns:
            A ``Placeholder`` with a deterministic replacement tag.
        """
        self._counters[label] += 1
        replacement = self._template.format(
            label=label,
            index=self._counters[label],
        )
        return Placeholder(
            original=original,
            label=label,
            replacement=replacement,
        )

    def _reset(self) -> None:
        """Clear per-label counters."""
        self._counters.clear()


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
        super().__init__()
        self._digest_length = digest_length
        self._template = template

    def create(self, original: str, label: str) -> Placeholder:
        """Mint a new hash-based placeholder.

        Args:
            original: The sensitive text fragment.
            label: The entity type (e.g. ``"PERSON"``).

        Returns:
            A ``Placeholder`` whose replacement is a deterministic
            hash tag derived from *original* and *label*.
        """
        bytes_ = original.encode()
        hash_ = hashlib.sha256(bytes_).hexdigest()
        digest = hash_[: self._digest_length]

        replacement = self._template.format(label=label, digest=digest)
        return Placeholder(
            original=original,
            label=label,
            replacement=replacement,
        )


class RedactPlaceholderFactory(IrreversiblePlaceholderFactory):
    """Replace all entities with a single opaque tag: ``[REDACTED]``.

    Every entity is mapped to the *same* replacement string regardless
    of its label or original text.  This makes deanonymization
    impossible no information leaks about whether two occurrences
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
        super().__init__()
        self._tag = tag

    def create(self, original: str, label: str) -> Placeholder:
        """Create a redacted placeholder.

        Args:
            original: The sensitive text fragment.
            label: The entity type.

        Returns:
            A ``Placeholder`` whose ``replacement`` is always ``self._tag``.
        """
        return Placeholder(
            original=original,
            label=label,
            replacement=self._tag,
        )
