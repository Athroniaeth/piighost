"""Composite detector: run several detectors and merge their detections."""

import asyncio

from piighost.components.detector.base import AnyDetector
from piighost.models import Detection


class CompositeDetector:
    """Run several detectors over the same text and merge their detections.

    A detector that is itself an AnyDetector, so it composes with the pipeline
    unchanged. It runs every child concurrently and concatenates their results
    in child order. It does not deduplicate. Overlaps and duplicates flow to the
    span-conflict stage, matching the AnyDetector contract.
    """

    def __init__(self, detectors: list[AnyDetector]) -> None:
        """Store the child detectors to run, in order."""
        self._detectors = detectors

    async def detect(self, text: str) -> list[Detection]:
        """Run every child concurrently and concatenate detections in order."""
        if not self._detectors:
            return []
        results = await asyncio.gather(
            *(detector.detect(text) for detector in self._detectors)
        )
        return [detection for result in results for detection in result]
