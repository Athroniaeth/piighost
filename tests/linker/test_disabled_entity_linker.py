"""Tests for ``DisabledEntityLinker``."""

from piighost.linker.entity import DisabledEntityLinker
from piighost.models import Detection, Entity, Span


def _det(text: str, label: str, start: int) -> Detection:
    return Detection(
        text=text,
        label=label,
        position=Span(start, start + len(text)),
        confidence=0.9,
    )


# ---------------------------------------------------------------------------
# link()
# ---------------------------------------------------------------------------


class TestLink:
    """Each detection becomes its own Entity. No expansion, no grouping."""

    def test_empty_detections(self) -> None:
        assert DisabledEntityLinker().link("text", []) == []

    def test_one_per_detection(self) -> None:
        detections = [_det("Patrick", "PERSON", 0), _det("Henri", "PERSON", 11)]
        entities = DisabledEntityLinker().link("Patrick et Henri", detections)
        assert len(entities) == 2
        assert all(len(e.detections) == 1 for e in entities)

    def test_same_text_not_grouped(self) -> None:
        # "Patrick" appears twice; ExactEntityLinker would group them, the
        # disabled linker keeps two distinct entities.
        d1 = _det("Patrick", "PERSON", 0)
        d2 = _det("Patrick", "PERSON", 20)
        entities = DisabledEntityLinker().link("Patrick et Patrick", [d1, d2])
        assert len(entities) == 2
        assert entities[0].detections[0] == d1
        assert entities[1].detections[0] == d2

    def test_no_expansion(self) -> None:
        # ExactEntityLinker would find "Patrick" at position 20 even if only
        # the first one was seeded; the disabled linker does not search.
        detections = [_det("Patrick", "PERSON", 0)]
        entities = DisabledEntityLinker().link(
            "Patrick et Patrick habite ici", detections
        )
        assert len(entities) == 1
        assert entities[0].detections == (detections[0],)


# ---------------------------------------------------------------------------
# link_entities()
# ---------------------------------------------------------------------------


class TestLinkEntities:
    """Cross-message linking is also disabled: known entities are ignored."""

    def test_empty(self) -> None:
        assert DisabledEntityLinker().link_entities([], []) == []

    def test_known_entities_ignored(self) -> None:
        known = [Entity(detections=(_det("Patrick", "PERSON", 0),))]
        current = [Entity(detections=(_det("Patrick", "PERSON", 0),))]
        out = DisabledEntityLinker().link_entities(current, known)
        # current entity returned untouched; not merged with the known one.
        assert out == current

    def test_returns_new_list(self) -> None:
        e = Entity(detections=(_det("Patrick", "PERSON", 0),))
        entities = [e]
        out = DisabledEntityLinker().link_entities(entities, [])
        assert out == entities
        assert out is not entities
