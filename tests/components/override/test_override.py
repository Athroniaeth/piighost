"""Tests for the DetectionOverride component."""

import pytest

from piighost.components.detector import ExactMatchDetector
from piighost.components.override import (
    AnyDetectionOverride,
    BlacklistStrategy,
    DetectionOverride,
    OverrideConflictStrategy,
)
from piighost.exceptions import ConflictingOverrideError
from piighost.models import Detection, Span


def _detection(
    start: int, end: int, text: str, label: str = "PERSON", confidence: float = 0.8
) -> Detection:
    """Build a detection covering [start, end) for the given text and label."""
    span = Span(start, end)
    return Detection(
        span=span,
        text=text,
        label=label,
        confidence=confidence,
    )


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """DetectionOverride is an AnyDetectionOverride."""
        assert isinstance(DetectionOverride(), AnyDetectionOverride)


class TestEmpty:
    async def test_no_lists_leave_detections_unchanged(self) -> None:
        """A component with neither list configured passes detections through."""
        primary = [_detection(0, 4, "Emma")]
        result = await DetectionOverride().apply("Emma", primary)
        assert result == primary


class TestWhitelist:
    async def test_adds_a_missed_value(self) -> None:
        """A whitelisted value absent from the detections is forced in."""
        override = DetectionOverride(whitelist=ExactMatchDetector({"Acme": "ORG"}))
        result = await override.apply("Acme rocks", [])
        assert len(result) == 1
        assert result[0].span == Span(0, 4)
        assert result[0].label == "ORG"
        assert result[0].confidence == 1.0

    async def test_replaces_an_overlapping_detection(self) -> None:
        """A forced detection replaces what it overlaps, the server label wins."""
        primary = [_detection(0, 8, "Emma Doe", label="COMPANY")]
        override = DetectionOverride(
            whitelist=ExactMatchDetector({"Emma Doe": "PERSON"})
        )
        result = await override.apply("Emma Doe called", primary)
        assert len(result) == 1
        assert result[0].label == "PERSON"


class TestBlacklistStrategies:
    async def test_exact_removes_the_identical_detection(self) -> None:
        """EXACT invalidates a detection with the same span and label."""
        primary = [_detection(6, 11, "Paris", label="LOCATION")]
        override = DetectionOverride(
            blacklist=ExactMatchDetector({"Paris": "LOCATION"})
        )
        assert await override.apply("Visit Paris", primary) == []

    async def test_exact_keeps_a_label_mismatch(self) -> None:
        """EXACT leaves a detection whose label differs from the blacklist's."""
        primary = [_detection(6, 11, "Paris", label="PERSON")]
        override = DetectionOverride(
            blacklist=ExactMatchDetector({"Paris": "LOCATION"})
        )
        assert await override.apply("Visit Paris", primary) == primary

    async def test_value_removes_the_value_everywhere(self) -> None:
        """VALUE invalidates every detection of the value, labels ignored."""
        primary = [
            _detection(6, 11, "Paris", label="PERSON"),
            _detection(16, 21, "Paris", label="LOCATION"),
        ]
        override = DetectionOverride(
            blacklist=ExactMatchDetector({"Paris": "LOCATION"}),
            blacklist_strategy=BlacklistStrategy.VALUE,
        )
        assert await override.apply("Visit Paris and Paris", primary) == []

    async def test_overlap_removes_what_it_touches(self) -> None:
        """OVERLAP invalidates any detection overlapping a blacklisted span."""
        primary = [_detection(6, 18, "Paris region", label="REGION")]
        override = DetectionOverride(
            blacklist=ExactMatchDetector({"Paris": "LOCATION"}),
            blacklist_strategy=BlacklistStrategy.OVERLAP,
        )
        assert await override.apply("Visit Paris region", primary) == []


class TestConflictStrategies:
    async def test_whitelist_wins_by_default(self) -> None:
        """A value on both lists is anonymized under WHITELIST_WINS."""
        override = DetectionOverride(
            whitelist=ExactMatchDetector({"Emma": "PERSON"}),
            blacklist=ExactMatchDetector({"Emma": "PERSON"}),
        )
        result = await override.apply("Hi Emma", [])
        assert len(result) == 1
        assert result[0].label == "PERSON"

    async def test_blacklist_wins_clears_the_forced_value(self) -> None:
        """Under BLACKLIST_WINS the cleared value stays clear."""
        override = DetectionOverride(
            whitelist=ExactMatchDetector({"Emma": "PERSON"}),
            blacklist=ExactMatchDetector({"Emma": "PERSON"}),
            conflict_strategy=OverrideConflictStrategy.BLACKLIST_WINS,
        )
        assert await override.apply("Hi Emma", []) == []

    async def test_raise_refuses_the_collision(self) -> None:
        """Under RAISE a span both forced and cleared is a loud error."""
        override = DetectionOverride(
            whitelist=ExactMatchDetector({"Emma": "PERSON"}),
            blacklist=ExactMatchDetector({"Emma": "LOCATION"}),
            conflict_strategy=OverrideConflictStrategy.RAISE,
        )
        with pytest.raises(ConflictingOverrideError, match="Emma"):
            await override.apply("Hi Emma", [])

    async def test_raise_applies_both_lists_when_disjoint(self) -> None:
        """RAISE without a collision still forces and clears normally."""
        override = DetectionOverride(
            whitelist=ExactMatchDetector({"Emma": "PERSON"}),
            blacklist=ExactMatchDetector({"Paris": "LOCATION"}),
            conflict_strategy=OverrideConflictStrategy.RAISE,
        )
        primary = [_detection(13, 18, "Paris", label="LOCATION")]
        result = await override.apply("Hi Emma, see Paris", primary)
        assert [detection.label for detection in result] == ["PERSON"]


class TestClearedValues:
    async def test_reports_the_blacklisted_values(self) -> None:
        """cleared_values returns the casefolded texts the blacklist matches."""
        override = DetectionOverride(
            blacklist=ExactMatchDetector({"Paris": "LOCATION"})
        )
        assert await override.cleared_values("Visit Paris") == frozenset({"paris"})

    async def test_is_empty_without_a_blacklist(self) -> None:
        """cleared_values is empty when no blacklist is configured."""
        assert await DetectionOverride().cleared_values("Visit Paris") == frozenset()
