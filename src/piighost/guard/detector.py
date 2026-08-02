"""Detector guard rail: re-run a detector and report residual PII."""

from piighost.detector.base import AnyDetector
from piighost.guard.base import GuardVerdict


class DetectorGuardRail:
    """Re-run a detector on anonymized text and report any PII that remains.

    It scans the output with the given detector and flags the verdict if the
    detector finds anything, carrying what it found as the residual detections.
    This only adds value with a detector different from the pipeline's:
    re-running the same one finds nothing, since the pipeline already anonymized
    everything it detects. A stronger or complementary detector, run on the short
    anonymized output as a second pass, catches what a cheaper primary detector
    missed. The synthetic placeholders are not PII-shaped, so a detector meant
    for real PII leaves them alone.

    Attributes:
        detector: The detector re-run on the anonymized text.
    """

    def __init__(self, detector: AnyDetector) -> None:
        """Store the detector to re-run on the anonymized text."""
        self.detector = detector

    async def check(self, text: str) -> GuardVerdict:
        """Return a verdict flagged when the detector finds PII in the text."""
        residual = await self.detector.detect(text)
        return GuardVerdict(flagged=bool(residual), detections=tuple(residual))
