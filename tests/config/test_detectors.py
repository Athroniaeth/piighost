"""Tests for the catalog, exact, and chunked detector config models."""

from typing import get_args

import pytest
from pydantic import TypeAdapter, ValidationError

from piighost.components.detector import (
    ChunkedDetector,
    ExactMatchDetector,
    RegexDetector,
)
from piighost.config.models.detector import (
    _CATALOGS,
    CatalogName,
    ChunkedDetectorConfig,
    DetectorConfig,
    ExactMatchDetectorConfig,
    RegexDetectorConfig,
)


@pytest.mark.parametrize("name", get_args(CatalogName))
def test_each_catalog_builds_non_empty_patterns(name: str) -> None:
    """Every catalog name wires a non-empty pattern set into the detector."""
    detector = RegexDetectorConfig(type="regex", catalogs=[name]).build()
    assert detector.patterns


def test_catalog_names_match_the_registry() -> None:
    """The CatalogName literal and the _CATALOGS registry stay in sync."""
    assert set(get_args(CatalogName)) == set(_CATALOGS)


class TestRegexCatalogs:
    def test_catalog_populates_patterns(self) -> None:
        """A catalog name fills the regex detector with the catalog's patterns."""
        detector = RegexDetectorConfig(type="regex", catalogs=["generic"]).build()
        assert isinstance(detector, RegexDetector)
        assert "EMAIL" in detector.patterns

    async def test_catalog_detector_detects(self) -> None:
        """A generic-catalog regex detector detects an email."""
        detector = RegexDetectorConfig(type="regex", catalogs=["generic"]).build()
        detections = await detector.detect("reach me at a@b.co")
        assert any(detection.label == "EMAIL" for detection in detections)

    def test_inline_overrides_catalog(self) -> None:
        """An inline pattern overrides a catalog pattern on the same label."""
        config = RegexDetectorConfig(
            type="regex", catalogs=["generic"], patterns={"EMAIL": "OVERRIDE"}
        )
        detector = config.build()
        assert detector.patterns["EMAIL"] == "OVERRIDE"

    def test_catalog_and_inline_both_survive(self) -> None:
        """Catalog and inline patterns on different labels both reach the detector."""
        config = RegexDetectorConfig(
            type="regex", catalogs=["generic"], patterns={"CUSTOM": "x"}
        )
        detector = config.build()
        assert "EMAIL" in detector.patterns
        assert "CUSTOM" in detector.patterns

    def test_neither_patterns_nor_catalogs_is_rejected(self) -> None:
        """A regex config with no inline patterns and no catalog fails validation."""
        with pytest.raises(ValidationError):
            RegexDetectorConfig(type="regex")

    def test_unknown_catalog_name_is_rejected(self) -> None:
        """An unknown catalog name fails validation."""
        with pytest.raises(ValidationError):
            RegexDetectorConfig(type="regex", catalogs=["mars"])


class TestExactDetectorConfig:
    def test_builds_an_exact_detector(self) -> None:
        """The exact config builds an ExactMatchDetector over its values."""
        detector = ExactMatchDetectorConfig(
            type="exact", values={"Emma": "PERSON"}
        ).build()
        assert isinstance(detector, ExactMatchDetector)
        assert detector.values == {"Emma": "PERSON"}

    async def test_exact_detector_detects(self) -> None:
        """An exact detector detects a configured literal value."""
        detector = ExactMatchDetectorConfig(
            type="exact", values={"Emma": "PERSON"}
        ).build()
        detections = await detector.detect("hello Emma")
        assert any(detection.label == "PERSON" for detection in detections)


class TestChunkedDetectorConfig:
    def test_wraps_a_detector(self) -> None:
        """The chunked config builds a ChunkedDetector around its inner detector."""
        config = ChunkedDetectorConfig(
            type="chunked",
            detector={"type": "regex", "patterns": {"EMAIL": "a@b"}},
        )
        assert isinstance(config.build(), ChunkedDetector)

    def test_rejects_overlap_not_below_size(self) -> None:
        """A chunk_overlap not smaller than chunk_size fails validation."""
        with pytest.raises(ValidationError):
            ChunkedDetectorConfig(
                type="chunked",
                detector={"type": "regex", "patterns": {"A": "a"}},
                chunk_size=100,
                chunk_overlap=100,
            )


class TestDetectorUnionWidening:
    def test_union_dispatches_exact(self) -> None:
        """The exact type dispatches to ExactMatchDetectorConfig through the union."""
        adapter = TypeAdapter(DetectorConfig)
        parsed = adapter.validate_python(
            {"type": "exact", "values": {"Emma": "PERSON"}}
        )
        assert isinstance(parsed, ExactMatchDetectorConfig)

    def test_union_dispatches_chunked(self) -> None:
        """The chunked type dispatches to ChunkedDetectorConfig through the union."""
        adapter = TypeAdapter(DetectorConfig)
        parsed = adapter.validate_python(
            {"type": "chunked", "detector": {"type": "regex", "patterns": {"A": "a"}}}
        )
        assert isinstance(parsed, ChunkedDetectorConfig)

    def test_guard_config_accepts_a_nested_exact_detector(self) -> None:
        """A guard detector config accepts the newly widened exact detector type."""
        from piighost.config.models.guard import GuardConfig

        adapter = TypeAdapter(GuardConfig)
        parsed = adapter.validate_python(
            {
                "type": "detector",
                "detector": {"type": "exact", "values": {"Emma": "PERSON"}},
            }
        )
        assert isinstance(parsed.detector, ExactMatchDetectorConfig)
