"""Anonymization pipeline: detect → expand → assign placeholders → replace.

Typical usage::

    pipeline = AnonymizationPipeline(extractor, matcher, replacer)
    result = pipeline.anonymize(text, ["person", "location", "company"])
    print(result.text)                  # anonymized
    print(pipeline.restore(result))     # back to original
"""

from maskara.anonymizer.extractor import EntityExtractor
from maskara.anonymizer.matcher import TextMatcher
from maskara.anonymizer.models import DetectedEntity
from maskara.span_replacer.models import ReplacementResult, Span
from maskara.span_replacer.replacer import SpanReplacer


class AnonymizationPipeline:
    """End-to-end anonymization backed by span-level replacement.

    The pipeline performs four steps:

    1. **Detect** — ask the extractor for entities (may return partial hits).
    2. **Expand** — for each unique entity text, use the matcher to find
       *every* occurrence in the source string.
    3. **Assign** — give each unique entity a numbered placeholder
       (e.g. ``{PERSON_1}``).
    4. **Replace** — delegate to ``SpanReplacer`` for an index-accurate
       replacement and a set of reverse spans.

    Args:
        extractor: Detects entities (GLiNER2, spaCy, mock …).
        matcher: Finds all occurrences of a surface form in text.
        replacer: Performs the actual span-based substitution.
    """

    def __init__(
        self,
        extractor: EntityExtractor,
        matcher: TextMatcher,
        replacer: SpanReplacer | None = None,
    ) -> None:
        self._extractor = extractor
        self._matcher = matcher
        self._replacer = replacer or SpanReplacer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def anonymize(
        self,
        text: str,
        labels: list[str],
    ) -> ReplacementResult:
        """Anonymize *text* and return the result with reverse spans.

        Args:
            text: The source string.
            labels: Entity types to detect (e.g. ``["person", "location"]``).

        Returns:
            A ``ReplacementResult`` with the anonymized text and the spans
            needed to restore the original.
        """
        detections = self._extractor.extract(text, labels)
        unique_detections = self._deduplicate(detections)
        mapping_placeholder = self._build_mapping_placeholder(unique_detections)
        all_spans = self._expand_to_spans(text, unique_detections, mapping_placeholder)
        clean_spans = self._resolve_overlaps(all_spans)
        return self._replacer.apply(text, clean_spans)

    def restore(self, result: ReplacementResult) -> str:
        """Undo an anonymization.

        Args:
            result: The ``ReplacementResult`` returned by ``anonymize``.

        Returns:
            The original text.
        """
        return self._replacer.restore(result)

    # ------------------------------------------------------------------
    # Internal steps
    # ------------------------------------------------------------------

    @staticmethod
    def _deduplicate(detections: list[DetectedEntity]) -> list[DetectedEntity]:
        """Keep one representative per unique entity text (highest confidence).

        Args:
            detections: Raw extractor output (may have duplicates).

        Returns:
            One ``DetectedEntity`` per unique ``text`` value, picking the
            highest-confidence hit when duplicates exist.
        """
        best: dict[str, DetectedEntity] = {}
        for det in detections:
            existing = best.get(det.text)
            if existing is None or det.confidence > existing.confidence:
                best[det.text] = det
        return list(best.values())

    @staticmethod
    def _build_mapping_placeholder(entities: list[DetectedEntity]) -> dict[str, str]:
        """Assign a numbered placeholder to each unique entity text.

        Args:
            entities: Deduplicated entities.

        Returns:
            Mapping ``entity_text → "{LABEL_N}"`` (e.g.
            ``{"Patrick": "{PERSON_1}", "Paris": "{LOCATION_1}"}``).
        """
        counters: dict[str, int] = {}
        mapping: dict[str, str] = {}
        for entity in entities:
            label = entity.label.upper()
            counters[label] = counters.get(label, 0) + 1
            mapping[entity.text] = f"{{{label}_{counters[label]}}}"
        return mapping

    def _expand_to_spans(
        self,
        text: str,
        entities: list[DetectedEntity],
        placeholder_map: dict[str, str],
    ) -> list[Span]:
        """Find every occurrence of each entity and build replacement Spans.

        Args:
            text: The source string.
            entities: Deduplicated entities (one per unique text).
            placeholder_map: The ``text → placeholder`` mapping.

        Returns:
            All ``Span`` objects (may contain overlaps at this stage).
        """
        spans: list[Span] = []
        for entity in entities:
            placeholder = placeholder_map[entity.text]
            for start, end in self._matcher.find_all(text, entity.text):
                spans.append(Span(start=start, end=end, replacement=placeholder))
        return spans

    @staticmethod
    def _resolve_overlaps(spans: list[Span]) -> list[Span]:
        """Discard overlapping spans, keeping the longest match.

        When two spans overlap, the one covering more characters wins.
        On ties, the one appearing first in the text wins.

        Args:
            spans: Possibly-overlapping replacement spans.

        Returns:
            Non-overlapping spans sorted by start index.
        """
        # Sort: longest first, then earliest start as tie-breaker.
        candidates = sorted(spans, key=lambda s: (-(s.end - s.start), s.start))
        kept: list[Span] = []
        for span in candidates:
            if not any(_overlaps(span, k) for k in kept):
                kept.append(span)
        return sorted(kept, key=lambda s: s.start)


def _overlaps(a: Span, b: Span) -> bool:
    """Return *True* if span *a* and span *b* share at least one index.

    Args:
        a: First span.
        b: Second span.

    Returns:
        Whether the two spans overlap.
    """
    return a.start < b.end and b.start < a.end
