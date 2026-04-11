"""Tests for ``ExactEntityLinker``."""

from piighost.linker.entity import ExactEntityLinker
from piighost.models import Detection, Entity, Span


def _det(
    text: str, label: str, start: int, end: int, confidence: float = 0.9
) -> Detection:
    return Detection(
        text=text, label=label, position=Span(start, end), confidence=confidence
    )


# ---------------------------------------------------------------------------
# Expansion finding missed occurrences
# ---------------------------------------------------------------------------


class TestExpansion:
    """The linker creates new detections for occurrences missed by the detector."""

    def test_expands_single_detection_to_all_occurrences(self) -> None:
        text = "Patrick est gentil. Patrick habite ici."
        detections = [_det("Patrick", "PERSON", 0, 7)]
        entities = ExactEntityLinker().link(text, detections)

        assert len(entities) == 1
        assert len(entities[0].detections) == 2

    def test_expanded_detection_has_confidence_one(self) -> None:
        text = "Patrick est gentil. Patrick habite ici."
        detections = [_det("Patrick", "PERSON", 0, 7, confidence=0.85)]
        entities = ExactEntityLinker().link(text, detections)

        confidences = {d.confidence for d in entities[0].detections}
        assert 0.85 in confidences  # original preserved
        assert 1.0 in confidences  # expanded detection

    def test_no_duplicate_when_already_detected(self) -> None:
        text = "Patrick est gentil. Patrick habite ici."
        detections = [
            _det("Patrick", "PERSON", 0, 7),
            _det("Patrick", "PERSON", 20, 27),
        ]
        entities = ExactEntityLinker().link(text, detections)

        assert len(entities) == 1
        assert len(entities[0].detections) == 2

    def test_does_not_expand_partial_matches(self) -> None:
        text = "Patrick et APatrick"
        detections = [_det("Patrick", "PERSON", 0, 7)]
        entities = ExactEntityLinker().link(text, detections)

        assert len(entities) == 1
        assert len(entities[0].detections) == 1


# ---------------------------------------------------------------------------
# Grouping detections of the same PII become one Entity
# ---------------------------------------------------------------------------


class TestGrouping:
    """Detections referring to the same PII are grouped into one Entity."""

    def test_same_text_same_label_grouped(self) -> None:
        text = "Patrick a dit bonjour à Patrick"
        detections = [
            _det("Patrick", "PERSON", 0, 7),
            _det("Patrick", "PERSON", 24, 31),
        ]
        entities = ExactEntityLinker().link(text, detections)
        assert len(entities) == 1

    def test_different_labels_not_grouped(self) -> None:
        text = "Patrick habite à Paris"
        detections = [
            _det("Patrick", "PERSON", 0, 7),
            _det("Paris", "LOCATION", 17, 22),
        ]
        entities = ExactEntityLinker().link(text, detections)
        assert len(entities) == 2

    def test_case_insensitive_grouping(self) -> None:
        text = "Patrick dit bonjour. PATRICK est là."
        detections = [
            _det("Patrick", "PERSON", 0, 7),
            _det("PATRICK", "PERSON", 21, 28),
        ]
        entities = ExactEntityLinker().link(text, detections)
        assert len(entities) == 1
        assert len(entities[0].detections) == 2

    def test_entity_label_from_first_detection(self) -> None:
        text = "Patrick habite ici"
        detections = [_det("Patrick", "PERSON", 0, 7)]
        entities = ExactEntityLinker().link(text, detections)
        assert entities[0].label == "PERSON"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Boundary conditions."""

    def test_empty_detections_returns_empty(self) -> None:
        assert ExactEntityLinker().link("du texte ici", []) == []

    def test_original_confidence_preserved(self) -> None:
        text = "Patrick est là"
        detections = [_det("Patrick", "PERSON", 0, 7, confidence=0.73)]
        entities = ExactEntityLinker().link(text, detections)
        assert entities[0].detections[0].confidence == 0.73

    def test_entities_sorted_by_earliest_position(self) -> None:
        text = "Paris est belle. Patrick est gentil."
        detections = [
            _det("Patrick", "PERSON", 17, 24),
            _det("Paris", "LOCATION", 0, 5),
        ]
        entities = ExactEntityLinker().link(text, detections)
        assert entities[0].label == "LOCATION"
        assert entities[1].label == "PERSON"

    def test_multiple_entities_with_expansion(self) -> None:
        text = "Patrick habite à Paris. Patrick aime Paris."
        detections = [
            _det("Patrick", "PERSON", 0, 7),
            _det("Paris", "LOCATION", 17, 22),
        ]
        entities = ExactEntityLinker().link(text, detections)

        assert len(entities) == 2
        for entity in entities:
            assert len(entity.detections) == 2


# ---------------------------------------------------------------------------
# link_entities — cross-message entity linking
# ---------------------------------------------------------------------------


def _entity(text: str, label: str, start: int = 0) -> Entity:
    """Build a single-detection entity for testing."""
    return Entity(
        detections=(Detection(text, label, Span(start, start + len(text)), 1.0),)
    )


class TestLinkEntities:
    """link_entities merges current entities with known ones by canonical key."""

    def test_links_same_canonical_text_and_label(self) -> None:
        known = [_entity("Patrick", "PERSON")]
        current = [_entity("patrick", "PERSON", start=10)]
        result = ExactEntityLinker().link_entities(current, known)

        assert len(result) == 1
        # Known detection comes first (preserves canonical)
        assert result[0].detections[0].text == "Patrick"

    def test_no_link_different_label(self) -> None:
        known = [_entity("Patrick", "LOCATION")]
        current = [_entity("Patrick", "PERSON", start=10)]
        result = ExactEntityLinker().link_entities(current, known)

        assert len(result) == 1
        assert result[0].label == "PERSON"
        # Not merged — only the current detection
        assert len(result[0].detections) == 1

    def test_no_link_when_no_known(self) -> None:
        current = [_entity("Patrick", "PERSON")]
        result = ExactEntityLinker().link_entities(current, [])

        assert result is current

    def test_no_link_when_no_current(self) -> None:
        known = [_entity("Patrick", "PERSON")]
        result = ExactEntityLinker().link_entities([], known)

        assert result == []

    def test_preserves_known_detections_first(self) -> None:
        """The merged entity has known detections before current ones."""
        known = [_entity("Patrick", "PERSON", start=0)]
        current = [_entity("patrick", "PERSON", start=20)]
        result = ExactEntityLinker().link_entities(current, known)

        texts = [d.text for d in result[0].detections]
        assert texts[0] == "Patrick"  # known first
        assert "patrick" in texts

    def test_no_duplicate_variant(self) -> None:
        """If the known entity already has 'Patrick', don't add it again."""
        known = [_entity("Patrick", "PERSON")]
        current = [_entity("Patrick", "PERSON", start=20)]
        result = ExactEntityLinker().link_entities(current, known)

        assert len(result) == 1
        # Known "Patrick" + current "Patrick" (same text, dedup by _add_variant later)
        texts = [d.text for d in result[0].detections]
        assert "Patrick" in texts

    def test_unmatched_entities_kept(self) -> None:
        """Entities not matching any known entity are returned as-is."""
        known = [_entity("Patrick", "PERSON")]
        current = [
            _entity("patrick", "PERSON", start=10),
            _entity("Paris", "LOCATION", start=30),
        ]
        result = ExactEntityLinker().link_entities(current, known)

        assert len(result) == 2
        labels = {e.label for e in result}
        assert labels == {"PERSON", "LOCATION"}


# ---------------------------------------------------------------------------
# min_text_length — filtering short fragments from expansion
# ---------------------------------------------------------------------------


class TestMinTextLength:
    """min_text_length prevents short detections from being expanded."""

    def test_skips_short_expansion(self) -> None:
        """A 1-char detection with min_text_length=2 is kept but not expanded."""
        text = "n est un n parmi n"
        detections = [_det("n", "PERSON", 0, 1)]
        linker = ExactEntityLinker(min_text_length=2)
        entities = linker.link(text, detections)

        assert len(entities) == 1
        assert len(entities[0].detections) == 1  # not expanded

    def test_allows_long_expansion(self) -> None:
        """A 7-char detection with min_text_length=2 is expanded normally."""
        text = "Patrick est gentil. Patrick habite ici."
        detections = [_det("Patrick", "PERSON", 0, 7)]
        linker = ExactEntityLinker(min_text_length=2)
        entities = linker.link(text, detections)

        assert len(entities) == 1
        assert len(entities[0].detections) == 2  # expanded

    def test_default_expands_all(self) -> None:
        """Default min_text_length=1 expands everything (backward-compatible)."""
        text = "n est un n parmi n"
        detections = [_det("n", "PERSON", 0, 1)]
        linker = ExactEntityLinker()
        entities = linker.link(text, detections)

        assert len(entities) == 1
        assert len(entities[0].detections) > 1  # expanded
