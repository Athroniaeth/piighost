"""Tests for ``DisabledSpanConflictResolver`` and ``DisabledEntityConflictResolver``."""

from piighost.models import Detection, Entity, Span
from piighost.resolver.entity import DisabledEntityConflictResolver
from piighost.resolver.span import DisabledSpanConflictResolver


def _det(label: str, start: int, end: int, confidence: float = 0.9) -> Detection:
    return Detection(
        text="x", label=label, position=Span(start, end), confidence=confidence
    )


def _ent(*detections: Detection) -> Entity:
    return Entity(detections=tuple(detections))


# ---------------------------------------------------------------------------
# DisabledSpanConflictResolver
# ---------------------------------------------------------------------------


class TestDisabledSpanConflictResolver:
    """Returns the input list unchanged regardless of overlaps."""

    def test_empty_list(self) -> None:
        assert DisabledSpanConflictResolver().resolve([]) == []

    def test_no_overlap_kept(self) -> None:
        detections = [_det("PERSON", 0, 7), _det("LOCATION", 11, 16)]
        assert DisabledSpanConflictResolver().resolve(detections) == detections

    def test_overlapping_spans_kept(self) -> None:
        # Both span (17, 24) and (17, 22) would normally conflict;
        # a disabled resolver keeps both.
        detections = [_det("PERSON", 17, 24, 0.91), _det("PERSON", 17, 22, 0.51)]
        assert DisabledSpanConflictResolver().resolve(detections) == detections

    def test_low_confidence_kept(self) -> None:
        # Confidence threshold filtering is also disabled.
        detections = [_det("PERSON", 0, 7, 0.01)]
        assert DisabledSpanConflictResolver().resolve(detections) == detections

    def test_returns_new_list(self) -> None:
        # Defensive: resolver should return a fresh list, not the same reference.
        detections = [_det("PERSON", 0, 7)]
        out = DisabledSpanConflictResolver().resolve(detections)
        assert out == detections
        assert out is not detections


# ---------------------------------------------------------------------------
# DisabledEntityConflictResolver
# ---------------------------------------------------------------------------


class TestDisabledEntityConflictResolver:
    """Returns the input list unchanged regardless of shared detections."""

    def test_empty_list(self) -> None:
        assert DisabledEntityConflictResolver().resolve([]) == []

    def test_distinct_entities_kept(self) -> None:
        e1 = _ent(_det("PERSON", 0, 7))
        e2 = _ent(_det("LOCATION", 11, 16))
        assert DisabledEntityConflictResolver().resolve([e1, e2]) == [e1, e2]

    def test_shared_detection_not_merged(self) -> None:
        # Two entities pointing to the same detection: would normally be merged.
        d = _det("PERSON", 0, 7)
        e1 = _ent(d)
        e2 = _ent(d)
        out = DisabledEntityConflictResolver().resolve([e1, e2])
        assert out == [e1, e2]

    def test_have_conflict_always_false(self) -> None:
        d = _det("PERSON", 0, 7)
        e1 = _ent(d)
        e2 = _ent(d)
        assert DisabledEntityConflictResolver().have_conflict(e1, e2) is False

    def test_returns_new_list(self) -> None:
        e1 = _ent(_det("PERSON", 0, 7))
        entities = [e1]
        out = DisabledEntityConflictResolver().resolve(entities)
        assert out == entities
        assert out is not entities
