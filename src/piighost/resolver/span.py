from typing import Protocol

from piighost.models import Detection


class AnySpanConflictResolver(Protocol):
    """Protocol defining the interface for span conflict resolvers.

    When multiple detections overlap (i.e. their spans share character
    positions), a resolver decides which detections to keep and which
    to discard.
    """

    def resolve(self, detections: list[Detection]) -> list[Detection]:
        """Resolve overlapping detections and return only the winners.

        Args:
            detections: The full list of detections, potentially with
                overlapping spans.

        Returns:
            A filtered list of detections with no overlapping spans.
        """
        ...


class BaseSpanConflictResolver:
    """Base class providing confidence threshold pre-filtering.

    Detections below ``confidence_threshold`` are removed entirely
    before overlap resolution.  This allows subclasses to focus on
    the overlap strategy without re-implementing threshold filtering.

    Args:
        confidence_threshold: Minimum confidence score to keep a
            detection.  Detections strictly below this value are
            discarded before overlap resolution.
            Defaults to ``0.0`` (keep everything, backward-compatible).
    """

    _confidence_threshold: float

    def __init__(self, confidence_threshold: float = 0.0) -> None:
        self._confidence_threshold = confidence_threshold

    def _pre_filter(self, detections: list[Detection]) -> list[Detection]:
        """Remove detections below the confidence threshold."""
        if self._confidence_threshold <= 0.0:
            return detections
        return [d for d in detections if d.confidence >= self._confidence_threshold]


class DisabledSpanConflictResolver:
    """Passthrough resolver that disables span conflict resolution.

    Returns the input list of detections unchanged. Useful when the
    detector already guarantees non-overlapping spans, or when the
    user explicitly wants overlapping detections to flow into entity
    linking (e.g. a PERSON and a LOCATION spanning the same characters
    that the linker should merge or treat as siblings).

    Example:
        >>> from piighost.models import Detection, Span
        >>> detections = [
        ...     Detection(label="PERSON", position=Span(17, 24), confidence=0.91),
        ...     Detection(label="PERSON", position=Span(17, 22), confidence=0.51),
        ... ]
        >>> resolver = DisabledSpanConflictResolver()
        >>> resolver.resolve(detections) == detections
        True
    """

    def resolve(self, detections: list[Detection]) -> list[Detection]:
        return list(detections)


class ConfidenceSpanConflictResolver(BaseSpanConflictResolver):
    """Resolver that keeps the detection with the highest confidence on overlap.

    When two or more detections have overlapping spans, only the one with
    the highest ``confidence`` score is retained. Non-overlapping detections
    are always kept.

    The algorithm sorts detections by descending confidence, then greedily
    accepts each detection only if it does not overlap with any already
    accepted detection.

    Args:
        confidence_threshold: Minimum confidence score to keep a
            detection.  Inherited from ``BaseSpanConflictResolver``.

    Example:
        >>> from piighost.models import Detection, Span
        >>> detections = [
        ...     Detection(label="PERSON", position=Span(17, 24), confidence=0.91),
        ...     Detection(label="PERSON", position=Span(17, 22), confidence=0.51),
        ...     Detection(label="LOCATION", position=Span(45, 51), confidence=1.0),
        ... ]
        >>> resolver = ConfidenceSpanConflictResolver()
        >>> resolved = resolver.resolve(detections)
        >>> [(d.label, d.confidence) for d in resolved]
        [('PERSON', 0.91), ('LOCATION', 1.0)]
    """

    def __init__(self, confidence_threshold: float = 0.0) -> None:
        super().__init__(confidence_threshold=confidence_threshold)

    def resolve(self, detections: list[Detection]) -> list[Detection]:
        """Keep the highest-confidence detection when spans overlap.

        Args:
            detections: The full list of detections, potentially with overlapping spans.

        Returns:
            A filtered list of detections with no overlapping spans,
            sorted by position (ascending ``start_pos``).
        """
        detections = self._pre_filter(detections)

        accepted: list[Detection] = []
        ranked = sorted(detections, key=lambda d: d.confidence, reverse=True)

        for detection in ranked:
            gen = (detection.position.overlaps(a.position) for a in accepted)
            if not any(gen):
                accepted.append(detection)

        accepted.sort(key=lambda d: d.position.start_pos)
        return accepted
