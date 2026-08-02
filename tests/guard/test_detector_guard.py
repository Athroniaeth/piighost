"""Tests for the DetectorGuardRail."""

from piighost.detector import ExactMatchDetector
from piighost.guard import AnyGuardRail, DetectorGuardRail


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """DetectorGuardRail is an AnyGuardRail."""
        assert isinstance(DetectorGuardRail(ExactMatchDetector({})), AnyGuardRail)


class TestCheck:
    async def test_clean_text_is_not_flagged(self) -> None:
        """Text the detector finds no PII in returns an unflagged verdict."""
        guard = DetectorGuardRail(ExactMatchDetector({"Emma": "PERSON"}))
        verdict = await guard.check("nothing to see here")
        assert verdict.flagged is False
        assert verdict.detections == ()

    async def test_residual_pii_is_flagged(self) -> None:
        """PII the detector still finds flags the verdict."""
        guard = DetectorGuardRail(ExactMatchDetector({"Emma": "PERSON"}))
        verdict = await guard.check("Emma slipped through")
        assert verdict.flagged is True

    async def test_verdict_carries_the_residual_detections(self) -> None:
        """The verdict exposes what leaked."""
        guard = DetectorGuardRail(ExactMatchDetector({"Emma": "PERSON"}))
        verdict = await guard.check("Emma slipped through")
        assert [detection.text for detection in verdict.detections] == ["Emma"]

    async def test_synthetic_placeholders_are_not_flagged(self) -> None:
        """A detector for real PII does not match the synthetic placeholder form."""
        guard = DetectorGuardRail(ExactMatchDetector({"Emma": "PERSON"}))
        verdict = await guard.check("Hello <<PERSON:1>>")
        assert verdict.flagged is False
