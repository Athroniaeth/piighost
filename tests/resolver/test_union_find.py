"""Union-find semantics and complexity guard for MergeEntityConflictResolver."""

from piighost.models import Detection, Entity, Span
from piighost.resolver.entity import MergeEntityConflictResolver


def _det(text: str, start: int) -> Detection:
    return Detection(
        text=text,
        label="PERSON",
        position=Span(start, start + len(text)),
        confidence=0.9,
    )


def test_transitive_merge_through_shared_detections():
    a, b, c = _det("Patrick", 0), _det("Patrick", 20), _det("patric", 40)
    e1 = Entity(detections=(a, b))
    e2 = Entity(detections=(b, c))
    e3 = Entity(detections=(c,))
    result = MergeEntityConflictResolver().resolve([e1, e2, e3])
    assert len(result) == 1
    assert set(result[0].detections) == {a, b, c}


def test_disjoint_entities_preserved_and_position_sorted():
    e_late = Entity(detections=(_det("Bob", 50),))
    e_early = Entity(detections=(_det("Alice", 0),))
    result = MergeEntityConflictResolver().resolve([e_late, e_early])
    assert [e.detections[0].text for e in result] == ["Alice", "Bob"]


def test_resolve_scales_to_large_inputs():
    # The old fixpoint loop was cubic; 2000 disjoint entities must resolve fast.
    entities = [Entity(detections=(_det(f"p{i}", i * 10),)) for i in range(2000)]
    result = MergeEntityConflictResolver().resolve(entities)
    assert len(result) == 2000
