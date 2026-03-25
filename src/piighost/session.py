"""Synchronous anonymization session with bidirectional lookup.

The ``AnonymizationSession`` combines an ``Anonymizer`` (detection +
replacement) with a ``PlaceholderRegistry`` (bidirectional lookup) to
provide a complete, **synchronous** API for multi-text anonymization
within a session.

Use this when you need session-aware deanonymization / reanonymization
but do **not** need async caching.  For async caching on top, see
``AnonymizationPipeline``.

Public API:

* ``anonymize`` – detect & replace PII, register placeholders.
* ``deanonymize_text`` – replace placeholder tags with originals.
* ``reanonymize_text`` – replace originals back to tags.
"""

import logging
from typing import Sequence

from piighost.anonymizer.anonymizer import Anonymizer
from piighost.anonymizer.models import (
    AnonymizationResult,
    IrreversibleAnonymizationError,
)
from piighost.registry import PlaceholderRegistry

logger = logging.getLogger(__name__)


class AnonymizationSession:
    """Synchronous session-aware anonymization with bidirectional lookup.

    Wraps an ``Anonymizer`` with a ``PlaceholderRegistry`` so that every
    ``anonymize`` call automatically registers its placeholders for
    subsequent ``deanonymize_text`` / ``reanonymize_text`` calls.

    This is the recommended entry point for **non-async** use cases
    such as batch processing, CLI tools, or REST endpoints that do not
    need cross-session caching.

    Args:
        anonymizer: The anonymization engine.
        registry: Bidirectional placeholder lookup.  Defaults to a
            fresh ``PlaceholderRegistry``.  Pass a shared instance to
            allow multiple sessions (or standalone code) to share the
            same mapping.

    Example:
        >>> session = AnonymizationSession(anonymizer=my_anonymizer)
        >>> result = session.anonymize("Patrick habite a Paris.")
        >>> result.anonymized_text
        '<<PERSON_1>> habite a <<LOCATION_1>>.'
        >>> session.deanonymize_text("Cherche <<PERSON_1>>")
        'Cherche Patrick'
        >>> session.reanonymize_text("Resultat pour Patrick a Paris")
        'Resultat pour <<PERSON_1>> a <<LOCATION_1>>'
    """

    def __init__(
        self,
        anonymizer: Anonymizer,
        registry: PlaceholderRegistry | None = None,
    ) -> None:
        self._anonymizer = anonymizer
        self._registry = registry if registry is not None else PlaceholderRegistry()
        # Inject the registry into the anonymizer so it uses the
        # registry for placeholder lookup instead of its own factory
        # cache, eliminating duplicate state.
        if self._anonymizer.registry is None:
            self._anonymizer.registry = self._registry

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def anonymize(
        self,
        text: str,
        active_labels: Sequence[str] | None = None,
    ) -> AnonymizationResult:
        """Anonymise *text* and register the resulting placeholders.

        Args:
            text: The source string.
            active_labels: Optional runtime filter forwarded to the
                detector.  When *None*, the detector uses all its
                configured labels.

        Returns:
            The ``AnonymizationResult`` with anonymised text,
            placeholders, and reverse spans.
        """
        result = self._anonymizer.anonymize(text, active_labels)

        if result.anonymized_text != text:
            self._registry.register(result)
            logger.debug(
                "Anonymised text: %d placeholder(s)",
                len(result.placeholders),
            )

        return result

    def deanonymize_text(self, text: str) -> str:
        """Replace every known placeholder tag in *text* with its original.

        This performs **string-based** replacement (not span-based) so it
        works on *any* string derived from an anonymised text, including
        LLM-generated tool-call arguments.

        For **span-based** exact reversal of a specific
        ``AnonymizationResult``, use ``Anonymizer.deanonymize`` instead.

        Args:
            text: A string potentially containing placeholder tags.

        Returns:
            The string with placeholders restored to original values.

        Raises:
            IrreversibleAnonymizationError: If the factory or registry
                is not reversible.
        """
        self._check_reversible()
        return self._registry.deanonymize(text)

    def reanonymize_text(self, text: str) -> str:
        """Replace every known original value in *text* with its placeholder tag.

        This is the inverse of ``deanonymize_text``.

        Args:
            text: A string potentially containing original values.

        Returns:
            The string with original values replaced by placeholder tags.

        Raises:
            IrreversibleAnonymizationError: If the factory or registry
                is not reversible.
        """
        self._check_reversible()
        return self._registry.reanonymize(text)

    @property
    def registry(self) -> PlaceholderRegistry:
        """The underlying placeholder registry (read-only access)."""
        return self._registry

    def reset(self) -> None:
        """Clear all state for a fresh session.

        Resets the ``Anonymizer``'s factory cache/counters and clears
        the ``PlaceholderRegistry`` in place (preserving shared
        references).
        """
        self._anonymizer.reset()
        self._registry.clear()

    # -----------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------

    def _check_reversible(self) -> None:
        """Raise if the anonymizer or registry is not reversible."""
        self._anonymizer.check_reversible()
        if not self._registry.reversible:
            raise IrreversibleAnonymizationError(
                "The registry contains non-reversible placeholders "
                "(multiple originals share the same replacement tag). "
                "Deanonymization requires a ReversiblePlaceholderFactory "
                "(e.g. CounterPlaceholderFactory or HashPlaceholderFactory)."
            )
