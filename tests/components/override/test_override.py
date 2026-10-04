"""Tests for the DetectionOverride component."""

import pytest

from piighost.components.detector import ExactMatchDetector
from piighost.components.override import (
    AllowListStrategy,
    AnyDetectionOverride,
    DenyListStrategy,
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


class TestDenyList:
    async def test_adds_a_missed_value(self) -> None:
        """A value on the deny list absent from the detections is forced in."""
        override = DetectionOverride(deny_list=ExactMatchDetector({"Acme": "ORG"}))
        result = await override.apply("Acme rocks", [])
        assert len(result) == 1
        assert result[0].span == Span(0, 4)
        assert result[0].label == "ORG"
        assert result[0].confidence == 1.0

    async def test_replaces_an_overlapping_detection(self) -> None:
        """A forced detection replaces what it overlaps, the server label wins."""
        primary = [_detection(0, 8, "Emma Doe", label="COMPANY")]
        override = DetectionOverride(
            deny_list=ExactMatchDetector({"Emma Doe": "PERSON"})
        )
        result = await override.apply("Emma Doe called", primary)
        assert len(result) == 1
        assert result[0].label == "PERSON"

    async def test_keeps_the_detector_order_on_one_span(self) -> None:
        """Two detections on one span stay in detector order, not label order."""
        primary = [
            _detection(0, 4, "Emma", label="SECOND"),
            _detection(0, 4, "Emma", label="FIRST"),
        ]
        override = DetectionOverride(deny_list=ExactMatchDetector({"Acme": "ORG"}))
        result = await override.apply("Emma at Acme", primary)
        assert [d.label for d in result] == ["SECOND", "FIRST", "ORG"]


class TestAllowListStrategies:
    async def test_exact_removes_the_identical_detection(self) -> None:
        """EXACT invalidates a detection with the same span and label."""
        primary = [_detection(6, 11, "Paris", label="LOCATION")]
        override = DetectionOverride(
            allow_list=ExactMatchDetector({"Paris": "LOCATION"}),
            allow_list_strategy=AllowListStrategy.EXACT,
        )
        assert await override.apply("Visit Paris", primary) == []

    async def test_exact_keeps_a_label_mismatch(self) -> None:
        """EXACT leaves a detection whose label differs from the allow list's."""
        primary = [_detection(6, 11, "Paris", label="PERSON")]
        override = DetectionOverride(
            allow_list=ExactMatchDetector({"Paris": "LOCATION"}),
            allow_list_strategy=AllowListStrategy.EXACT,
        )
        assert await override.apply("Visit Paris", primary) == primary

    async def test_value_is_the_default_and_ignores_the_label(self) -> None:
        """The default strategy clears a value whatever label the allow list gives it."""
        primary = [_detection(6, 11, "Paris", label="PERSON")]
        override = DetectionOverride(
            allow_list=ExactMatchDetector({"Paris": "LOCATION"})
        )
        assert await override.apply("Visit Paris", primary) == []

    async def test_value_removes_the_value_everywhere(self) -> None:
        """VALUE invalidates every detection of the value, labels ignored."""
        primary = [
            _detection(6, 11, "Paris", label="PERSON"),
            _detection(16, 21, "Paris", label="LOCATION"),
        ]
        override = DetectionOverride(
            allow_list=ExactMatchDetector({"Paris": "LOCATION"}),
            allow_list_strategy=AllowListStrategy.VALUE,
        )
        assert await override.apply("Visit Paris and Paris", primary) == []

    async def test_overlap_removes_what_it_touches(self) -> None:
        """OVERLAP invalidates any detection overlapping a span on the allow list."""
        primary = [_detection(6, 18, "Paris region", label="REGION")]
        override = DetectionOverride(
            allow_list=ExactMatchDetector({"Paris": "LOCATION"}),
            allow_list_strategy=AllowListStrategy.OVERLAP,
        )
        assert await override.apply("Visit Paris region", primary) == []


class TestConflictStrategies:
    async def test_deny_list_wins_by_default(self) -> None:
        """A value on both lists is anonymized under DENY_LIST_WINS."""
        override = DetectionOverride(
            deny_list=ExactMatchDetector({"Emma": "PERSON"}),
            allow_list=ExactMatchDetector({"Emma": "PERSON"}),
        )
        result = await override.apply("Hi Emma", [])
        assert len(result) == 1
        assert result[0].label == "PERSON"

    async def test_allow_list_wins_clears_the_forced_value(self) -> None:
        """Under ALLOW_LIST_WINS the cleared value stays clear."""
        override = DetectionOverride(
            deny_list=ExactMatchDetector({"Emma": "PERSON"}),
            allow_list=ExactMatchDetector({"Emma": "PERSON"}),
            conflict_strategy=OverrideConflictStrategy.ALLOW_LIST_WINS,
        )
        assert await override.apply("Hi Emma", []) == []

    async def test_raise_refuses_the_collision(self) -> None:
        """Under RAISE a span both forced and cleared is a loud error."""
        override = DetectionOverride(
            deny_list=ExactMatchDetector({"Emma": "PERSON"}),
            allow_list=ExactMatchDetector({"Emma": "LOCATION"}),
            conflict_strategy=OverrideConflictStrategy.RAISE,
        )
        with pytest.raises(ConflictingOverrideError, match="Emma"):
            await override.apply("Hi Emma", [])

    async def test_raise_applies_both_lists_when_disjoint(self) -> None:
        """RAISE without a collision still forces and clears normally."""
        override = DetectionOverride(
            deny_list=ExactMatchDetector({"Emma": "PERSON"}),
            allow_list=ExactMatchDetector({"Paris": "LOCATION"}),
            conflict_strategy=OverrideConflictStrategy.RAISE,
        )
        primary = [_detection(13, 18, "Paris", label="LOCATION")]
        result = await override.apply("Hi Emma, see Paris", primary)
        assert [detection.label for detection in result] == ["PERSON"]


class TestClearedValues:
    async def test_reports_the_allow_listed_values(self) -> None:
        """cleared_values returns the casefolded texts the allow list matches."""
        override = DetectionOverride(
            allow_list=ExactMatchDetector({"Paris": "LOCATION"})
        )
        assert await override.cleared_values("Visit Paris") == frozenset({"paris"})

    async def test_is_empty_without_a_allow_list(self) -> None:
        """cleared_values is empty when no allow list is configured."""
        assert await DetectionOverride().cleared_values("Visit Paris") == frozenset()


class TestForcesValue:
    async def test_respect_provenance_never_forces(self) -> None:
        """The default strategy defers to provenance even on a deny list match."""
        override = DetectionOverride(deny_list=ExactMatchDetector({"Acme": "ORG"}))
        assert await override.forces_value("Acme") is False

    async def test_force_forces_a_matched_value(self) -> None:
        """FORCE claims a value the deny list matches in full."""
        override = DetectionOverride(
            deny_list=ExactMatchDetector({"Acme": "ORG"}),
            deny_list_strategy=DenyListStrategy.FORCE,
        )
        assert await override.forces_value("Acme") is True

    async def test_force_ignores_an_unmatched_value(self) -> None:
        """FORCE claims nothing the deny list does not match."""
        override = DetectionOverride(
            deny_list=ExactMatchDetector({"Acme": "ORG"}),
            deny_list_strategy=DenyListStrategy.FORCE,
        )
        assert await override.forces_value("Globex") is False


class TestUnicodeSpaces:
    async def test_value_clears_a_spelling_with_other_spaces(self) -> None:
        """VALUE compares by value key, so a no-break-space spelling is cleared too."""
        text = "Paul Martin, puis Paul\u00a0Martin"
        primary = [_detection(18, 29, "Paul\u00a0Martin", label="PERSON")]
        override = DetectionOverride(
            allow_list=ExactMatchDetector({"Paul Martin": "PERSON"}),
            allow_list_strategy=AllowListStrategy.VALUE,
        )
        assert await override.apply(text, primary) == []
