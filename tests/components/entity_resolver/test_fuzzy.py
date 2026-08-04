"""Tests for the FuzzyEntityResolver."""

from piighost.components.entity_resolver import AnyEntityResolver, FuzzyEntityResolver
from piighost.models import Detection, Entity, Span


def _entity(text: str, start: int = 0, label: str = "PERSON") -> Entity:
    """Build a one-detection entity for a text at a position."""
    span = Span(start, start + len(text))
    detection = Detection(
        span=span,
        text=text,
        label=label,
        confidence=0.9,
    )
    return Entity((detection,))


def _pair_similarity(first: str, second: str) -> float:
    """Stub similarity scoring only the pairs the chain test declares."""
    scores = {
        frozenset(("aaa", "bbb")): 0.9,
        frozenset(("bbb", "ccc")): 0.9,
        frozenset(("aaa", "ccc")): 0.1,
    }
    return scores.get(frozenset((first, second)), 0.0)


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """FuzzyEntityResolver is an AnyEntityResolver."""
        assert isinstance(FuzzyEntityResolver(), AnyEntityResolver)


class TestResolve:
    def test_merges_near_duplicate_values(self) -> None:
        """A typo variant of a value merges into one entity."""
        first = _entity("Patrick", start=0)
        second = _entity("Patrik", start=20)
        resolved = FuzzyEntityResolver().resolve([first, second])
        assert len(resolved) == 1
        assert resolved[0].detections == first.detections + second.detections

    def test_keeps_distinct_values_apart(self) -> None:
        """Values below the threshold stay separate entities."""
        first = _entity("Patrick", start=0)
        second = _entity("Liam", start=20)
        resolved = FuzzyEntityResolver().resolve([first, second])
        assert len(resolved) == 2

    def test_never_merges_across_labels(self) -> None:
        """An identical value under another label stays a separate entity."""
        person = _entity("Emma", start=0, label="PERSON")
        company = _entity("Emma", start=20, label="COMPANY")
        resolved = FuzzyEntityResolver().resolve([person, company])
        assert len(resolved) == 2

    def test_case_variants_read_as_one_value(self) -> None:
        """Texts differing only by case merge into one entity."""
        upper = _entity("EMMA", start=0)
        lower = _entity("emma", start=20)
        resolved = FuzzyEntityResolver().resolve([upper, lower])
        assert len(resolved) == 1

    def test_threshold_is_respected(self) -> None:
        """A stricter threshold keeps a looser match apart."""
        first = _entity("Patrick", start=0)
        second = _entity("Patricia", start=20)
        merged = FuzzyEntityResolver(threshold=0.85).resolve([first, second])
        kept = FuzzyEntityResolver(threshold=0.95).resolve([first, second])
        assert len(merged) == 1
        assert len(kept) == 2

    def test_merged_detections_are_position_ordered(self) -> None:
        """A merged entity's detections come back in position order."""
        late = _entity("Patrik", start=20)
        early = _entity("Patrick", start=0)
        resolved = FuzzyEntityResolver().resolve([late, early])
        assert len(resolved) == 1
        assert resolved[0].detections == early.detections + late.detections


class TestAnchorClustering:
    def test_similarity_chains_do_not_over_merge(self) -> None:
        """A joins B through their anchor, but C, unlike A, starts its own group.

        Similarity is not transitive: with A similar to B and B similar to C but
        A far from C, a transitive closure would collapse all three. Anchor
        clustering compares C against the first group's anchor A only, so C
        stays out.
        """
        a = _entity("aaa", start=0)
        b = _entity("bbb", start=10)
        c = _entity("ccc", start=20)
        resolver = FuzzyEntityResolver(similarity=_pair_similarity)
        resolved = resolver.resolve([a, b, c])
        assert len(resolved) == 2
        assert resolved[0].detections == a.detections + b.detections
        assert resolved[1].detections == c.detections
