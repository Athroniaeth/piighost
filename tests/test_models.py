"""Tests for :mod:`piighost.models`, focused on representations and serialization."""

from __future__ import annotations

import pytest

from piighost.models import Detection, Entity, Span


class TestDetectionRepr:
    """Detection masks raw PII in its repr; metadata stays visible."""

    def _make(self, text: str = "Patrick Durand") -> Detection:
        return Detection(
            text=text,
            label="PERSON",
            position=Span(start_pos=0, end_pos=len(text)),
            confidence=0.99,
        )

    def test_repr_masks_text_but_shows_metadata(self) -> None:
        detection = self._make("Patrick")
        rendered = repr(detection)
        assert "Detection(" in rendered
        assert "Patrick" not in rendered
        assert "text='P***'" in rendered
        assert "label='PERSON'" in rendered
        assert "position=Span(start_pos=0, end_pos=7)" in rendered
        assert "confidence=0.99" in rendered

    def test_str_matches_repr(self) -> None:
        # Dataclass str() falls back to __repr__.
        detection = self._make("Patrick")
        assert str(detection) == repr(detection)

    def test_raw_text_accessible_via_attribute(self) -> None:
        detection = self._make("Patrick")
        assert detection.text == "Patrick"

    def test_raw_text_accessible_via_to_dict(self) -> None:
        detection = self._make("Patrick")
        assert detection.to_dict()["text"] == "Patrick"

    def test_hash_uses_raw_text(self) -> None:
        detection = self._make("Patrick")
        assert detection.hash.startswith("Patrick:PERSON:")


class TestEntityRepr:
    """Entity repr nests Detections, whose raw PII text stays masked."""

    def test_entity_repr_masks_nested_detection_text(self) -> None:
        detection = Detection(
            text="Patrick",
            label="PERSON",
            position=Span(0, 7),
            confidence=1.0,
        )
        entity = Entity(detections=(detection,))
        rendered = repr(entity)
        assert "Entity(" in rendered
        assert "Detection(" in rendered
        assert "Patrick" not in rendered
        assert "text='P***'" in rendered

    def test_entity_with_multiple_detections_masks_each(self) -> None:
        entity = Entity(
            detections=(
                Detection(
                    text="Patrick", label="PERSON", position=Span(0, 7), confidence=0.9
                ),
                Detection(
                    text="Patrice",
                    label="PERSON",
                    position=Span(20, 27),
                    confidence=0.8,
                ),
            )
        )
        rendered = repr(entity)
        assert "Patrick" not in rendered
        assert "Patrice" not in rendered
        # Both detections share the same first char, so both mask to 'P***'.
        assert rendered.count("text='P***'") == 2


class TestSpanRepr:
    """Span contains only positional metadata, not PII; repr stays verbose."""

    def test_span_repr_shows_positions(self) -> None:
        span = Span(start_pos=5, end_pos=12)
        assert repr(span) == "Span(start_pos=5, end_pos=12)"


class TestDetectionSerialization:
    """Detection.to_dict and from_dict roundtrip without loss."""

    def _make(self) -> Detection:
        return Detection(
            text="Patrick",
            label="PERSON",
            position=Span(start_pos=0, end_pos=7),
            confidence=0.9,
        )

    def test_to_dict_schema(self) -> None:
        assert self._make().to_dict() == {
            "text": "Patrick",
            "label": "PERSON",
            "start_pos": 0,
            "end_pos": 7,
            "confidence": 0.9,
        }

    def test_roundtrip(self) -> None:
        original = self._make()
        assert Detection.from_dict(original.to_dict()) == original


class TestEntitySerialization:
    """Entity.to_dict and from_dict roundtrip without loss."""

    def _make(self) -> Entity:
        return Entity(
            detections=(
                Detection(
                    text="Patrick",
                    label="PERSON",
                    position=Span(start_pos=0, end_pos=7),
                    confidence=0.9,
                ),
                Detection(
                    text="Patric",
                    label="PERSON",
                    position=Span(start_pos=20, end_pos=26),
                    confidence=0.8,
                ),
            )
        )

    def test_to_dict_has_detections_list(self) -> None:
        data = self._make().to_dict()
        assert list(data) == ["detections"]
        assert len(data["detections"]) == 2

    def test_roundtrip(self) -> None:
        original = self._make()
        assert Entity.from_dict(original.to_dict()) == original


def test_span_rejects_inverted_bounds():
    with pytest.raises(ValueError):
        Span(start_pos=5, end_pos=2)


def test_span_rejects_negative_start():
    with pytest.raises(ValueError):
        Span(start_pos=-1, end_pos=2)


def test_detection_repr_masks_pii():
    d = Detection(text="Patrick", label="PERSON", position=Span(0, 7), confidence=0.9)
    assert "Patrick" not in repr(d)
    assert "P***" in repr(d)
    # to_dict stays raw: it is the explicit serialization path.
    assert d.to_dict()["text"] == "Patrick"


def test_entity_canonical_properties():
    d = Detection(text="Patrick", label="PERSON", position=Span(0, 7), confidence=0.9)
    e = Entity(detections=(d,))
    assert e.canonical == "patrick"
    assert e.canonical_key == ("patrick", "PERSON")
