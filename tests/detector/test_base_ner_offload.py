"""BaseNERDetector offloads sync inference off the event loop (P1a).

Uses a tiny concrete subclass with a blocking sync "model" so the test
needs no heavy NER dependency.
"""

import asyncio
import time

from piighost.detector.base import BaseNERDetector
from piighost.models import Detection

INFER = 0.1


class _BlockingDetector(BaseNERDetector):
    """Detector whose 'inference' is a blocking time.sleep run via _run_blocking."""

    def __init__(self, max_concurrency=None):
        super().__init__(labels=["PERSON"], max_concurrency=max_concurrency)
        self.peak = 0
        self._live = 0

    def _infer(self, text):
        self._live += 1
        self.peak = max(self.peak, self._live)
        time.sleep(INFER)  # releases the GIL, like real torch/spacy inference
        self._live -= 1
        return []

    async def detect(self, text):
        await self._run_blocking(self._infer, text)
        return []


async def test_detect_does_not_block_the_event_loop():
    det = _BlockingDetector()
    ticks = 0

    async def heartbeat():
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    hb = asyncio.create_task(heartbeat())
    await asyncio.gather(det.detect("a"), det.detect("b"), det.detect("c"))
    hb.cancel()

    # The loop kept running (heartbeat ticked) instead of being frozen.
    assert ticks > 0


async def test_concurrent_detects_run_in_parallel_without_semaphore():
    det = _BlockingDetector()
    t0 = time.perf_counter()
    await asyncio.gather(*(det.detect(str(i)) for i in range(4)))
    elapsed = time.perf_counter() - t0
    # 4 parallel sleeps finish in ~max, not ~sum.
    assert elapsed < 3 * INFER
    assert det.peak >= 2  # genuinely concurrent


async def test_semaphore_bounds_concurrency():
    det = _BlockingDetector(max_concurrency=1)
    await asyncio.gather(*(det.detect(str(i)) for i in range(3)))
    assert det.peak == 1  # serialized by the semaphore
