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


def test_fuzzy_chain_does_not_collapse_distinct_groups():
    """Pairwise-similar chains must not transitively merge distinct PIIs.

    sims at threshold 0.85: alexandree~alexnndre 0.94 (merge),
    alexnndre~leexandre 0.852, alexandree~leexandre 0.81 (no merge
    with the group anchor), so leexandre starts its own group.
    """
    from piighost.resolver.entity import FuzzyEntityConflictResolver

    e1 = Entity(detections=(_det("alexandree", 0),))
    e2 = Entity(detections=(_det("alexnndre", 20),))
    e3 = Entity(detections=(_det("leexandre", 40),))
    result = FuzzyEntityConflictResolver(threshold=0.85).resolve([e1, e2, e3])
    assert len(result) == 2


def test_resolve_scales_with_late_conflict_chain():
    """Guard against the old fixpoint loop (restarted a full O(n^2) scan
    after every merge: cubic on inputs whose merges happen late).

    900 disjoint entities followed by a 100-entity shared-detection
    chain took ~20s on the old implementation, <1s on union-find.
    """
    import time

    disjoint = [Entity(detections=(_det(f"p{i}", i * 20),)) for i in range(900)]
    shared = [_det("chain", 20000 + i * 10) for i in range(101)]
    chain = [Entity(detections=(shared[i], shared[i + 1])) for i in range(100)]
    start = time.perf_counter()
    result = MergeEntityConflictResolver().resolve(disjoint + chain)
    elapsed = time.perf_counter() - start
    assert len(result) == 901
    assert elapsed < 5.0
