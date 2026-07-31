"""Tests for the DetectorGuardRail."""

import pytest

from piighost.detector import ExactMatchDetector
from piighost.exceptions import PIIRemainingError
from piighost.guard import AnyGuardRail, DetectorGuardRail


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """DetectorGuardRail is an AnyGuardRail."""
        assert isinstance(DetectorGuardRail(ExactMatchDetector({})), AnyGuardRail)


class TestCheck:
    async def test_clean_text_passes(self) -> None:
        """Text the detector finds no PII in raises nothing."""
        guard = DetectorGuardRail(ExactMatchDetector({"Emma": "PERSON"}))
        await guard.check("nothing to see here")

    async def test_residual_pii_raises(self) -> None:
        """PII the detector still finds raises PIIRemainingError."""
        guard = DetectorGuardRail(ExactMatchDetector({"Emma": "PERSON"}))
        with pytest.raises(PIIRemainingError):
            await guard.check("Emma slipped through")

    async def test_error_carries_the_residual_detections(self) -> None:
        """The raised error exposes what leaked."""
        guard = DetectorGuardRail(ExactMatchDetector({"Emma": "PERSON"}))
        with pytest.raises(PIIRemainingError) as info:
            await guard.check("Emma slipped through")
        assert [detection.text for detection in info.value.detections] == ["Emma"]

    async def test_synthetic_placeholders_are_not_flagged(self) -> None:
        """A detector for real PII does not match the synthetic placeholder form."""
        guard = DetectorGuardRail(ExactMatchDetector({"Emma": "PERSON"}))
        await guard.check("Hello <<PERSON:1>>")
