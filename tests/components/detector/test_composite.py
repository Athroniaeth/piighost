"""Tests for the CompositeDetector."""

import asyncio

from piighost.components.detector import (
    AnyDetector,
    CompositeDetector,
    ExactMatchDetector,
)
from piighost.models import Detection


class TestConformance:
    def test_satisfies_the_detector_port(self) -> None:
        """CompositeDetector is an AnyDetector."""
        assert isinstance(CompositeDetector([]), AnyDetector)


class TestDetect:
    async def test_merges_children_in_order(self) -> None:
        """Detections are concatenated in child-detector order."""
        composite = CompositeDetector(
            [
                ExactMatchDetector({"Emma": "PERSON"}),
                ExactMatchDetector({"Paris": "LOCATION"}),
            ]
        )
        detections = await composite.detect("Emma in Paris")
        labels = [detection.label for detection in detections]
        assert labels == ["PERSON", "LOCATION"]

    async def test_empty_detector_list_returns_empty(self) -> None:
        """A composite with no child returns no detection."""
        assert await CompositeDetector([]).detect("Emma in Paris") == []

    async def test_runs_children_concurrently(self) -> None:
        """Children are awaited concurrently, not strictly one after another."""
        both_started = asyncio.Event()
        started = 0

        class _Blocking:
            async def detect(self, text: str) -> list[Detection]:
                nonlocal started
                started += 1
                if started == 2:
                    both_started.set()
                await both_started.wait()
                return []

        composite = CompositeDetector([_Blocking(), _Blocking()])
        # If the children ran sequentially the first would wait forever, since
        # the event is only set once both have started. gather lets both start.
        await asyncio.wait_for(composite.detect("x"), timeout=1.0)
