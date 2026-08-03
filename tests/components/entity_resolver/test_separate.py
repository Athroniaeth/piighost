"""Tests for the SeparateEntityResolver."""

from piighost.components.entity_resolver import AnyEntityResolver, SeparateEntityResolver
from piighost.models import Detection, Entity, Span


def _detection(
    start: int, end: int, text: str = "Emma", label: str = "PERSON"
) -> Detection:
    """Build a detection covering [start, end) for the given text and label."""
    return Detection(span=Span(start, end), text=text, label=label, confidence=0.9)


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """SeparateEntityResolver is an AnyEntityResolver."""
        assert isinstance(SeparateEntityResolver(), AnyEntityResolver)


class TestResolve:
    def test_largest_keeps_the_shared_detection(self) -> None:
        """A-B-C and C-D share C: the larger A-B-C keeps it, so C-D becomes D."""
        a, b, c, d = (
            _detection(0, 1),
            _detection(2, 3),
            _detection(4, 5),
            _detection(6, 7),
        )
        resolved = SeparateEntityResolver().resolve([Entity((a, b, c)), Entity((c, d))])
        assert {entity.detections for entity in resolved} == {(a, b, c), (d,)}

    def test_tie_goes_to_the_earliest_entity(self) -> None:
        """On equal size, the entity whose occurrence comes first wins the detection."""
        shared = _detection(4, 5)
        first = Entity((_detection(0, 1), shared))
        second = Entity((shared, _detection(6, 7)))
        resolved = SeparateEntityResolver().resolve([second, first])
        winner = next(e for e in resolved if shared in e.detections)
        assert winner.spans[0] == Span(0, 1)

    def test_disjoint_entities_are_unchanged(self) -> None:
        """Entities that share no detection pass through untouched."""
        first = Entity((_detection(0, 1),))
        second = Entity((_detection(2, 3),))
        resolved = SeparateEntityResolver().resolve([first, second])
        assert set(resolved) == {first, second}

    def test_entity_left_empty_is_dropped(self) -> None:
        """An entity whose every detection is taken away disappears."""
        a, b = _detection(0, 1), _detection(2, 3)
        resolved = SeparateEntityResolver().resolve([Entity((a, b)), Entity((a, b))])
        assert resolved == [Entity((a, b))]

    def test_single_entity_is_returned_unchanged(self) -> None:
        """A lone entity comes back as itself."""
        entity = Entity((_detection(0, 1), _detection(2, 3)))
        assert SeparateEntityResolver().resolve([entity]) == [entity]
