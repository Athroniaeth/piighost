"""Tests for the ExactEntityLinker."""

from piighost.linker import AnyEntityLinker, ExactEntityLinker
from piighost.models import Detection, Span


def _detection(start: int, end: int, text: str, label: str = "PERSON") -> Detection:
    """Build a detection covering [start, end) for the given text and label."""
    span = Span(start, end)
    return Detection(
        span=span,
        text=text,
        label=label,
        confidence=0.9,
    )


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """ExactEntityLinker is an AnyEntityLinker."""
        assert isinstance(ExactEntityLinker(), AnyEntityLinker)


class TestLink:
    def test_groups_repeats_of_one_value(self) -> None:
        """Two occurrences of the same value become one entity."""
        first = _detection(0, 4, "Emma")
        second = _detection(9, 13, "Emma")
        entities = ExactEntityLinker().link([first, second])
        assert len(entities) == 1
        assert entities[0].detections == (first, second)

    def test_groups_case_variants(self) -> None:
        """Detections differing only by case share an entity."""
        first = _detection(0, 4, "Emma")
        second = _detection(9, 13, "emma")
        entities = ExactEntityLinker().link([first, second])
        assert len(entities) == 1

    def test_keeps_first_spelling_as_canonical(self) -> None:
        """The entity's text is the first occurrence seen."""
        first = _detection(0, 4, "Emma")
        second = _detection(9, 13, "emma")
        entities = ExactEntityLinker().link([first, second])
        assert entities[0].text == "Emma"

    def test_separates_by_label(self) -> None:
        """Same text under different labels stays in separate entities."""
        person = _detection(0, 4, "Lyon", label="PERSON")
        location = _detection(9, 13, "Lyon", label="LOCATION")
        entities = ExactEntityLinker().link([person, location])
        assert len(entities) == 2

    def test_separates_distinct_values(self) -> None:
        """Different values become different entities."""
        emma = _detection(0, 4, "Emma")
        liam = _detection(9, 13, "Liam")
        entities = ExactEntityLinker().link([emma, liam])
        assert len(entities) == 2

    def test_keeps_first_occurrence_order(self) -> None:
        """Entities come out in the order their value first appears."""
        emma = _detection(0, 4, "Emma")
        liam = _detection(9, 13, "Liam")
        entities = ExactEntityLinker().link([emma, liam])
        assert [entity.text for entity in entities] == ["Emma", "Liam"]

    def test_no_detections_yields_no_entities(self) -> None:
        """Linking nothing returns no entities."""
        assert ExactEntityLinker().link([]) == []
