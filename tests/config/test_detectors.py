"""Tests for the catalog, exact, and chunked detector config models."""

from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from piighost.components.detector import (
    ChunkedDetector,
    ExactMatchDetector,
    RegexDetector,
)
from piighost.config.models.detector import (
    ChunkedDetectorConfig,
    DetectorConfig,
    ExactMatchDetectorConfig,
    RegexDetectorConfig,
)

CATALOG = {
    "catalog:piighost/generic:fab51b33": {"EMAIL": r"\S+@\S+", "URL": r"https?://\S+"},
    "catalog:piighost/logs:fd79aec6": {"EMAIL": "FROM_LOGS", "TOKEN": r"tok_\w+"},
}
"""What the fake catalog answers for each reference, in registry order."""


@pytest.fixture
def fake_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    """Answer every pull from CATALOG, so no test reaches the network."""
    monkeypatch.setattr("piighost.config.models.detector.pull", CATALOG.__getitem__)


class TestRegexCatalogs:
    def test_a_catalog_reference_is_accepted(self) -> None:
        """A config can name a reviewed pattern group instead of copying it."""
        config = RegexDetectorConfig(
            type="regex", catalogs=["catalog:piighost/logs:fd79aec6"]
        )
        assert config.catalogs == ["catalog:piighost/logs:fd79aec6"]

    def test_a_1x_hub_reference_is_still_accepted(self) -> None:
        """A config written for 1.x, with hub: references, still validates."""
        config = RegexDetectorConfig(
            type="regex", catalogs=["hub:piighost/logs:fd79aec6"]
        )
        assert config.catalogs == ["hub:piighost/logs:fd79aec6"]

    @pytest.mark.parametrize("name", ["generic", "us", "eu", "fr"])
    def test_a_removed_catalog_name_points_to_its_catalog_group(
        self, name: str
    ) -> None:
        """A pre-2.0 catalog name is refused with the reference that replaces it."""
        bad_kwargs: dict[str, Any] = {"type": "regex", "catalogs": [name]}
        with pytest.raises(ValidationError, match=f"catalog:piighost/{name}"):
            RegexDetectorConfig(**bad_kwargs)

    def test_a_malformed_reference_is_rejected(self) -> None:
        """A typo fails at load time rather than as a malformed URL later."""
        bad_kwargs: dict[str, Any] = {"type": "regex", "catalogs": ["catalog:Logs"]}
        with pytest.raises(ValidationError, match="unknown catalog"):
            RegexDetectorConfig(**bad_kwargs)

    def test_neither_patterns_nor_catalogs_is_rejected(self) -> None:
        """A regex config with no inline patterns and no catalog fails validation."""
        with pytest.raises(ValidationError):
            RegexDetectorConfig(type="regex")

    @pytest.mark.usefixtures("fake_catalog")
    def test_a_catalog_is_pulled_at_build(self) -> None:
        """Building a config that names a catalog fetches its patterns."""
        detector = RegexDetectorConfig(
            type="regex", catalogs=["catalog:piighost/generic:fab51b33"]
        ).build()
        assert isinstance(detector, RegexDetector)
        assert detector.patterns == CATALOG["catalog:piighost/generic:fab51b33"]

    @pytest.mark.usefixtures("fake_catalog")
    def test_catalogs_merge_in_order_then_inline_patterns(self) -> None:
        """A later catalog overrides an earlier one, and an inline pattern both."""
        detector = RegexDetectorConfig(
            type="regex",
            catalogs=[
                "catalog:piighost/generic:fab51b33",
                "catalog:piighost/logs:fd79aec6",
            ],
            patterns={"TOKEN": "INLINE"},
        ).build()
        assert isinstance(detector, RegexDetector)
        assert detector.patterns == {
            "EMAIL": "FROM_LOGS",
            "URL": r"https?://\S+",
            "TOKEN": "INLINE",
        }


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
