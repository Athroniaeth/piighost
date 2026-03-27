"""Bidirectional placeholder registry for deanonymization and reanonymization.

The ``PlaceholderRegistry`` maintains a deduplicated mapping between
placeholder tags and their original values, accumulated across multiple
anonymization passes within a session.

It is usable **standalone** (CLI, batch processing, REST API) or as a
building block inside ``AnonymizationPipeline`` (which adds async caching).

Public API:

* ``register`` / ``register_placeholder`` – feed results or individual
  placeholders into the registry.
* ``deanonymize`` – replace every known tag with its original value.
* ``reanonymize`` – replace every known original value with its tag.
* ``lookup_replacement`` / ``lookup_original`` – point lookups.

All replacement operations are **string-based** (``str.replace``).  For
**span-based** exact reversal of a specific ``AnonymizationResult``, use
``Anonymizer.deanonymize`` or ``SpanReplacer.restore`` instead.
"""

from piighost.anonymizer.models import AnonymizationResult, Placeholder


class PlaceholderRegistry:
    """Bidirectional lookup between original values and placeholder tags.

    The registry stores :class:`Placeholder` objects indexed two ways:

    * **by replacement** – ``tag → Placeholder`` (for deanonymization).
    * **by original** – ``(original, label) → Placeholder`` (for
      reanonymization and duplicate detection).

    Both dicts use insertion-order iteration (Python 3.7+), which
    preserves the order in which entities were first seen.

    Example:
        >>> from piighost.anonymizer.models import Placeholder, AnonymizationResult
        >>> registry = PlaceholderRegistry()
        >>> registry.register_placeholder(
        ...     Placeholder("Patrick", "PERSON", "<<PERSON_1>>"),
        ... )
        >>> registry.deanonymize("Bonjour <<PERSON_1>>")
        'Bonjour Patrick'
        >>> registry.reanonymize("Bonjour Patrick")
        'Bonjour <<PERSON_1>>'
    """

    def __init__(self) -> None:
        self._by_replacement: dict[str, Placeholder] = {}
        self._by_original: dict[tuple[str, str], Placeholder] = {}

    # -----------------------------------------------------------------
    # Registration
    # -----------------------------------------------------------------

    def register(self, result: AnonymizationResult) -> None:
        """Register all placeholders from an anonymization result.

        Args:
            result: A result previously returned by ``Anonymizer.anonymize``.
        """
        for placeholder in result.placeholders:
            self.register_placeholder(placeholder)

    def register_placeholder(self, placeholder: Placeholder) -> None:
        """Register a single placeholder.

        If the same ``(original, label)`` pair is already registered, the
        existing entry is kept (first-writer-wins).

        Args:
            placeholder: The placeholder to register.
        """
        key = (placeholder.original, placeholder.label)
        if key not in self._by_original:
            self._by_original[key] = placeholder
            self._by_replacement[placeholder.replacement] = placeholder

    # -----------------------------------------------------------------
    # Text replacement
    # -----------------------------------------------------------------

    def deanonymize(self, text: str) -> str:
        """Replace every known placeholder tag in *text* with its original.

        This is a **string-based** operation: it works on any string that
        contains placeholder tags, including LLM-generated output or
        tool-call arguments that were never directly anonymized.

        Tags are replaced **longest-first** so that a longer tag is never
        partially matched by a shorter one that happens to be a substring.

        Args:
            text: A string potentially containing placeholder tags.

        Returns:
            The string with placeholders restored to original values.
        """
        for replacement, placeholder in sorted(
            self._by_replacement.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            text = text.replace(replacement, placeholder.original)
        return text

    def reanonymize(self, text: str) -> str:
        """Replace every known original value in *text* with its placeholder tag.

        This is the inverse of :meth:`deanonymize`.

        Originals are replaced **longest-first** so that a longer original
        (e.g. ``"Patrick"``) is matched before a shorter substring
        (e.g. ``"Pat"``).

        Args:
            text: A string potentially containing original values.

        Returns:
            The string with original values replaced by placeholder tags.
        """
        for placeholder in sorted(
            self._by_original.values(),
            key=lambda p: len(p.original),
            reverse=True,
        ):
            text = text.replace(placeholder.original, placeholder.replacement)
        return text

    # -----------------------------------------------------------------
    # Point lookups
    # -----------------------------------------------------------------

    def lookup_replacement(self, tag: str) -> Placeholder | None:
        """Find the placeholder for a given replacement tag.

        Args:
            tag: A placeholder tag (e.g. ``"<<PERSON_1>>"``).

        Returns:
            The matching ``Placeholder``, or *None* if unknown.
        """
        return self._by_replacement.get(tag)

    def lookup_original(self, original: str, label: str) -> Placeholder | None:
        """Find the placeholder for a given ``(original, label)`` pair.

        Args:
            original: The original sensitive text.
            label: The entity type.

        Returns:
            The matching ``Placeholder``, or *None* if unknown.
        """
        return self._by_original.get((original, label))

    # -----------------------------------------------------------------
    # Introspection
    # -----------------------------------------------------------------

    @property
    def placeholders(self) -> tuple[Placeholder, ...]:
        """All registered placeholders (deduplicated, insertion order)."""
        return tuple(self._by_replacement.values())

    @property
    def reversible(self) -> bool:
        """Whether all registered placeholders have unique replacement tags.

        Returns ``True`` when every ``replacement`` string maps to exactly
        one ``original``.  Returns ``False`` when multiple originals share
        the same tag (e.g. ``RedactPlaceholderFactory`` maps everything to
        ``[REDACTED]``).

        An empty registry is considered reversible.
        """
        return len(self._by_replacement) >= len(self._by_original)

    def clear(self) -> None:
        """Remove all registered placeholders.

        Unlike creating a new ``PlaceholderRegistry``, this preserves the
        object identity useful when the registry is shared between
        multiple sessions or components.
        """
        self._by_replacement.clear()
        self._by_original.clear()

    def __len__(self) -> int:
        """Number of unique placeholders registered."""
        return len(self._by_original)

    def __bool__(self) -> bool:
        """True if the registry contains at least one placeholder."""
        return bool(self._by_original)
