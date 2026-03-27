"""High-level anonymiser that orchestrates the full pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from piighost.anonymizer.detector import EntityDetector
from piighost.anonymizer.models import (
    AnonymizationResult,
    Placeholder,
)
from piighost.anonymizer.occurrence import OccurrenceFinder, RegexOccurrenceFinder
from piighost.anonymizer.placeholder import (
    CounterPlaceholderFactory,
    PlaceholderFactory,
)
from piighost.span_replacer.models import ReplacementResult, Span
from piighost.span_replacer.replacer import SpanReplacer

if TYPE_CHECKING:
    from piighost.registry import PlaceholderRegistry


class Anonymizer:
    """Orchestrate entity detection, occurrence expansion, and replacement.

    The pipeline works in four stages:

    1. **Detect** – the ``EntityDetector`` returns raw entity spans.
    2. **Expand** – for each unique detected text, the
       ``OccurrenceFinder`` locates *every* occurrence in the source
       (not just the ones the model found).
    3. **Map** – a ``Placeholder`` is resolved for each unique
       ``(text, label)`` pair.
    4. **Replace** – the ``SpanReplacer`` applies the substitutions and
       computes reverse spans for deanonymization.

    **Placeholder resolution** depends on whether a ``registry`` is
    attached:

    * **Without registry** (standalone): the ``PlaceholderFactory``'s
      built-in cache (``get_or_create``) handles deduplication.
    * **With registry** (via ``AnonymizationSession``): the registry
      is the single source of truth ``factory.create()`` is called
      only for genuinely new entities, eliminating duplicate caching.

    All collaborators are injected so they can be swapped or mocked.

    Args:
        detector: NER back-end (e.g. ``GlinerDetector``).
        occurrence_finder: Strategy for locating all fragment positions.
            Defaults to ``RegexOccurrenceFinder``.
        placeholder_factory: Strategy for generating replacement tags.
            Defaults to ``CounterPlaceholderFactory``.
        replacer: The span replacement engine.
            Defaults to a vanilla ``SpanReplacer``.

    Example:
        >>> anonymizer = Anonymizer(detector=my_gliner_detector)
        >>> result = anonymizer.anonymize(
        ...     "Patrick habite à Paris. Patrick aime Paris.",
        ...     labels=["PERSON", "LOCATION"],
        ... )
        >>> result.anonymized_text
        '<<PERSON_1>> habite à <<LOCATION_1>>. <<PERSON_1>> aime <<LOCATION_1>>.'
    """

    def __init__(
        self,
        detector: EntityDetector,
        occurrence_finder: OccurrenceFinder | None = None,
        placeholder_factory: PlaceholderFactory | None = None,
        replacer: SpanReplacer | None = None,
    ) -> None:
        self._detector = detector
        self._occurrence_finder = occurrence_finder or RegexOccurrenceFinder()
        self._placeholder_factory = placeholder_factory or CounterPlaceholderFactory()
        self._replacer = replacer or SpanReplacer()
        self._registry: PlaceholderRegistry | None = None

    @property
    def registry(self) -> PlaceholderRegistry | None:
        """The attached ``PlaceholderRegistry``, or *None*.

        When set, the anonymizer uses the registry for placeholder
        lookup instead of the factory's internal cache, eliminating
        duplicate state.  Typically set by ``AnonymizationSession``.
        """
        return self._registry

    @registry.setter
    def registry(self, value: PlaceholderRegistry | None) -> None:
        self._registry = value

    def _resolve_placeholder(self, original: str, label: str) -> Placeholder:
        """Look up or create a placeholder for *(original, label)*.

        When a ``registry`` is attached, it is consulted first; on miss
        ``factory.create()`` mints a fresh placeholder and registers it.

        Without a registry the factory's own ``get_or_create`` cache
        handles deduplication (standalone mode).
        """
        if self._registry is not None:
            existing = self._registry.lookup_original(original, label)
            if existing is not None:
                return existing
            placeholder = self._placeholder_factory.create(original, label)
            self._registry.register_placeholder(placeholder)
            return placeholder
        return self._placeholder_factory.get_or_create(original, label)

    def anonymize(
        self,
        text: str,
        active_labels: Sequence[str] | None = None,
    ) -> AnonymizationResult:
        """Anonymise *text* by detecting and replacing sensitive entities.

        Args:
            text: The source string.
            active_labels: Optional runtime filter forwarded to the detector.
                When *None*, the detector uses all its configured labels.

        Returns:
            An ``AnonymizationResult`` containing the anonymised text,
            the placeholders created, and the reverse spans for
            deanonymization.
        """
        # Build spans for every occurrence of every unique entity.
        spans: list[Span] = []
        placeholders: list[Placeholder] = []
        occupied: set[tuple[int, int]] = set()

        entities = self._detector.detect(text, active_labels)

        # Deduplicate: keep the first (highest-position) entity per
        # unique (text, label) pair.  Order does not matter because
        # occurrence expansion will relocate every position anyway.
        unique_entities = {(ent.text, ent.label): ent for ent in entities}

        for ent_text, ent_label in unique_entities:
            placeholder = self._resolve_placeholder(ent_text, ent_label)
            placeholders.append(placeholder)

            occurrences = self._occurrence_finder.find_all(text, ent_text)
            for start, end in occurrences:
                if (start, end) in occupied:
                    continue
                occupied.add((start, end))
                span = Span(
                    start=start,
                    end=end,
                    replacement=placeholder.replacement,
                )
                spans.append(span)

        replacement_result = self._replacer.apply(text, spans)

        return AnonymizationResult(
            original_text=text,
            anonymized_text=replacement_result.text,
            placeholders=tuple(placeholders),
            reverse_spans=replacement_result.reverse_spans,
        )

    def reset(self) -> None:
        """Clear factory state for a new session.

        Resets the ``PlaceholderFactory``'s internal cache and counters
        so that subsequent ``anonymize`` calls start with a clean slate.
        """
        self._placeholder_factory.reset()

    @property
    def reversible(self) -> bool:
        """Whether the placeholder factory supports deanonymization."""
        return self._placeholder_factory.reversible

    def check_reversible(self) -> None:
        """Raise if the placeholder factory does not support deanonymization.

        Raises:
            IrreversibleAnonymizationError: If the placeholder factory
                is not reversible (e.g. ``RedactPlaceholderFactory``).
        """
        self._placeholder_factory.check_reversible()

    def deanonymize(self, result: AnonymizationResult) -> str:
        """Restore the original text from an ``AnonymizationResult``.

        This performs **span-based** exact reversal using the reverse
        spans stored in *result*.  It only works on the exact text
        returned by ``anonymize``.

        For **string-based** reversal that works on any derived text
        (LLM output, tool arguments, etc.), use
        ``PlaceholderRegistry.deanonymize`` instead.

        Args:
            result: A result previously returned by ``anonymize``.

        Returns:
            The original text before anonymization.

        Raises:
            IrreversibleAnonymizationError: If the placeholder factory
                is not reversible (e.g. ``RedactPlaceholderFactory``).
        """
        self.check_reversible()

        replacement_result = ReplacementResult(
            text=result.anonymized_text,
            reverse_spans=result.reverse_spans,
        )
        return self._replacer.restore(replacement_result)
