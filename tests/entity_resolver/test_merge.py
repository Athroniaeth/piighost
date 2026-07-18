"""Tests for the MergeEntityResolver."""

from piighost.entity_resolver import AnyEntityResolver, MergeEntityResolver
from piighost.models import Detection, Entity, Span


def _detection(start: int, end: int, text: str = "Emma", label: str = "PERSON") -> Detection:
    """Build a detection covering [start, end) for the given text and label."""
    return Detection(span=Span(start, end), text=text, label=label, confidence=0.9)


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """MergeEntityResolver is an AnyEntityResolver."""
        assert isinstance(MergeEntityResolver(), AnyEntityResolver)


class TestResolve:
    def test_merges_entities_that_share_a_detection(self) -> None:
        """A-B-C and C-D share C, so they merge into one entity."""
        a, b, c, d = _detection(0, 1), _detection(2, 3), _detection(4, 5), _detection(6, 7)
        first = Entity((a, b, c))
        second = Entity((c, d))
        resolved = MergeEntityResolver().resolve([first, second])
        assert len(resolved) == 1
        assert resolved[0].detections == (a, b, c, d)

    def test_does_not_merge_disjoint_entities(self) -> None:
        """Entities that share no detection stay separate."""
        a, b = _detection(0, 1), _detection(2, 3)
        first = Entity((a,))
        second = Entity((b,))
        resolved = MergeEntityResolver().resolve([first, second])
        assert len(resolved) == 2

    def test_merges_transitively(self) -> None:
        """A-B, B-C, and C-D chain through shared detections into one entity."""
        a, b, c, d = _detection(0, 1), _detection(2, 3), _detection(4, 5), _detection(6, 7)
        resolved = MergeEntityResolver().resolve(
            [Entity((a, b)), Entity((b, c)), Entity((c, d))]
        )
        assert len(resolved) == 1
        assert set(resolved[0].detections) == {a, b, c, d}

    def test_deduplicates_shared_detections(self) -> None:
        """A detection shared by two entities appears once in the merged entity."""
        a, b, c = _detection(0, 1), _detection(2, 3), _detection(4, 5)
        resolved = MergeEntityResolver().resolve([Entity((a, b, c)), Entity((c,))])
        assert resolved[0].detections.count(c) == 1

    def test_single_entity_is_returned_unchanged(self) -> None:
        """A lone entity comes back as itself."""
        a, b = _detection(0, 1), _detection(2, 3)
        entity = Entity((a, b))
        assert MergeEntityResolver().resolve([entity]) == [entity]

    def test_no_entities_yields_no_entities(self) -> None:
        """Resolving nothing returns no entities."""
        assert MergeEntityResolver().resolve([]) == []
