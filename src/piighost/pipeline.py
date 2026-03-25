"""Async anonymization pipeline with caching.

The ``AnonymizationPipeline`` extends ``AnonymizationSession`` with
async result caching via a ``PlaceholderStore``.

Use ``AnonymizationSession`` when you need synchronous, session-aware
anonymization without caching.  Use ``AnonymizationPipeline`` when you
also need cross-request persistence (Redis, database, etc.).

Public API:

* ``anonymize`` (async) – detect & replace PII, cache the result.
* ``deanonymize_text`` (sync) – replace placeholder tags with originals.
* ``reanonymize_text`` (sync) – replace originals back to tags.
"""

import logging

from piighost.anonymizer.anonymizer import Anonymizer
from piighost.anonymizer.models import AnonymizationResult
from piighost.registry import PlaceholderRegistry
from piighost.session import AnonymizationSession
from piighost.store import InMemoryPlaceholderStore, PlaceholderStore, text_hash

logger = logging.getLogger(__name__)


class AnonymizationPipeline:
    """Async anonymization pipeline with caching and bidirectional lookup.

    Wraps an ``AnonymizationSession`` and adds an async
    ``PlaceholderStore`` for cross-request result caching.  All
    synchronous operations (``deanonymize_text``, ``reanonymize_text``)
    delegate to the underlying session.

    Args:
        anonymizer: The anonymization engine.
        store: Async key-value backend.  Defaults to
            ``InMemoryPlaceholderStore``.
        registry: Bidirectional placeholder lookup.  Defaults to a
            fresh ``PlaceholderRegistry``.  Pass a shared instance to
            allow multiple pipelines (or standalone code) to share the
            same mapping.

    Example:
        >>> pipeline = AnonymizationPipeline(anonymizer=my_anonymizer)
        >>> result = await pipeline.anonymize("Patrick habite a Paris.")
        >>> result.anonymized_text
        '<<PERSON_1>> habite a <<LOCATION_1>>.'
        >>> pipeline.deanonymize_text("Cherche <<PERSON_1>>")
        'Cherche Patrick'
        >>> pipeline.reanonymize_text("Resultat pour Patrick a Paris")
        'Resultat pour <<PERSON_1>> a <<LOCATION_1>>'
    """

    def __init__(
        self,
        anonymizer: Anonymizer,
        store: PlaceholderStore | None = None,
        registry: PlaceholderRegistry | None = None,
    ) -> None:
        self._session = AnonymizationSession(anonymizer, registry)
        self._store = store if store is not None else InMemoryPlaceholderStore()

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    async def anonymize(self, text: str) -> AnonymizationResult:
        """Anonymise *text*, cache the result, and register it.

        If the exact text has already been processed (cache hit), the
        stored result is returned and its placeholders are registered in
        the in-memory registry (if not already present).

        Args:
            text: The source string.

        Returns:
            The ``AnonymizationResult`` (possibly cached).
        """
        key = text_hash(text)
        cached = await self._store.get(key)

        if cached is not None:
            self._session.registry.register(cached)
            return cached

        result = self._session.anonymize(text)

        if result.anonymized_text != text:
            await self._store.set(key, result)
            logger.debug(
                "Anonymised text (hash=%s): %d placeholder(s)",
                key[:12],
                len(result.placeholders),
            )

        return result

    def deanonymize_text(self, text: str) -> str:
        """Replace every known placeholder tag in *text* with its original.

        Delegates to the underlying ``AnonymizationSession``.
        """
        return self._session.deanonymize_text(text)

    def reanonymize_text(self, text: str) -> str:
        """Replace every known original value in *text* with its placeholder tag.

        Delegates to the underlying ``AnonymizationSession``.
        """
        return self._session.reanonymize_text(text)

    def reset(self) -> None:
        """Reset session state (factory cache + registry).

        The async ``PlaceholderStore`` is **not** cleared — only the
        in-memory session state is reset.  Call this between
        conversations or when the anonymizer configuration changes.
        """
        self._session.reset()

    @property
    def session(self) -> AnonymizationSession:
        """The underlying synchronous session."""
        return self._session

    @property
    def registry(self) -> PlaceholderRegistry:
        """The underlying placeholder registry (read-only access)."""
        return self._session.registry
