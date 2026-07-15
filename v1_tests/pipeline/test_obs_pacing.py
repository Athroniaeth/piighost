"""The pipeline must not block the event loop with time.sleep."""

import time

from piighost.anonymizer import Anonymizer
from piighost.detector.base import ExactMatchDetector
from piighost.pipeline.base import AnonymizationPipeline


async def test_no_pacing_overhead_without_observation_backend():
    pipe = AnonymizationPipeline(
        detector=ExactMatchDetector([("Patrick", "PERSON")]),
        anonymizer=Anonymizer(),
    )
    start = time.perf_counter()
    for i in range(50):
        await pipe.anonymize(f"Bonjour Patrick numero {i}")
    elapsed = time.perf_counter() - start
    # 50 runs x 4 stages x 1ms sleep would be >= 0.2s; without pacing
    # this loop finishes far quicker.
    assert elapsed < 0.15


def test_source_has_no_blocking_sleep():
    import inspect
    import piighost.pipeline.base as base
    import piighost.pipeline.thread as thread

    assert "time.sleep" not in inspect.getsource(base)
    assert "time.sleep" not in inspect.getsource(thread)
