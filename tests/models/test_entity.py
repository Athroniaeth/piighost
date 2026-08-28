"""Tests for the Entity model."""

import dataclasses

import pytest

from piighost.exceptions import EmptyEntityError, MixedLabelError
from piighost.models import Detection, Entity, Span


def _detection(
    start: int, end: int, label: str = "PERSON", text: str = "Emma"
) -> Detection:
    """Build a detection at the given span with the given label and text."""
    span = Span(start, end)
    return Detection(
        span=span,
        label=label,
        confidence=0.9,
        text=text,
    )


class TestConstruction:
    def test_stores_detections(self) -> None:
        """An entity stores the tuple of detections it groups."""
        d = _detection(0, 4)
        entity = Entity(detections=(d,))
        assert entity.detections == (d,)

    def test_frozen(self) -> None:
        """Assigning to a field raises because the dataclass is frozen."""
        entity = Entity(detections=(_detection(0, 4),))
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(entity, "detections", ())  # noqa: B010  # dynamic set: the frozen guard must raise, a direct assignment would not type-check

    def test_no_instance_dict(self) -> None:
        """A frozen slotted instance has no __dict__."""
        assert not hasattr(Entity(detections=(_detection(0, 4),)), "__dict__")

    def test_hashable_and_dedupes_by_value(self) -> None:
        """Equal entities hash equal and deduplicate in a set."""
        a = Entity(detections=(_detection(0, 4),))
        b = Entity(detections=(_detection(0, 4),))
        assert len({a, b}) == 1


class TestDerivedProperties:
    def test_label_comes_from_detections(self) -> None:
        """The entity label is the shared label of its detections."""
        entity = Entity(detections=(_detection(0, 4, label="EMAIL"),))
        assert entity.label == "EMAIL"

    def test_text_is_the_first_occurrence(self) -> None:
        """The canonical text is the first detection's text."""
        first = _detection(0, 7, text="Patrick")
        second = _detection(40, 47, text="patrick")
        entity = Entity(detections=(first, second))
        assert entity.text == "Patrick"

    def test_spans_gathers_every_occurrence(self) -> None:
        """spans returns the span of every detection, in order."""
        first = _detection(0, 7, text="Patrick")
        second = _detection(40, 47, text="patrick")
        entity = Entity(detections=(first, second))
        assert entity.spans == (Span(0, 7), Span(40, 47))


class TestValidation:
    def test_empty_detections_raise(self) -> None:
        """An entity with no detections raises EmptyEntityError."""
        with pytest.raises(EmptyEntityError):
            Entity(detections=())

    def test_mixed_labels_raise(self) -> None:
        """Detections with differing labels raise MixedLabelError."""
        person = _detection(0, 4, label="PERSON")
        email = _detection(5, 9, label="EMAIL")
        with pytest.raises(MixedLabelError):
            Entity(detections=(person, email))
