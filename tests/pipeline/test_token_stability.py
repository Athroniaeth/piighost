"""Placeholder identity must be stable across messages and workers."""

from aiocache import SimpleMemoryCache

from piighost.anonymizer import Anonymizer
from piighost.detector.base import ExactMatchDetector
from piighost.pipeline.thread import ThreadAnonymizationPipeline


def _detector() -> ExactMatchDetector:
    return ExactMatchDetector([("Patrick", "PERSON"), ("Alice", "PERSON")])


def _pipeline(cache=None) -> ThreadAnonymizationPipeline:
    return ThreadAnonymizationPipeline(
        detector=_detector(), anonymizer=Anonymizer(), cache=cache
    )


async def test_counter_not_stolen_by_earlier_position_in_later_message():
    pipe = _pipeline()
    a1, _ = await pipe.anonymize("Bonjour Patrick", thread_id="t")
    # Alice appears at position 0, earlier than Patrick's old span(8, 15):
    # she must still get the NEXT counter, not steal <<PERSON:1>>.
    a2, _ = await pipe.anonymize("Alice est la", thread_id="t")
    assert a1 == "Bonjour <<PERSON:1>>"
    assert a2 == "<<PERSON:2>> est la"

    restored = await pipe.deanonymize_with_ent(
        "<<PERSON:1>> et <<PERSON:2>>", thread_id="t"
    )
    assert restored == "Patrick et Alice"


async def test_token_ordering_shared_across_workers_via_cache():
    cache = SimpleMemoryCache()
    worker_a = _pipeline(cache)
    worker_b = _pipeline(cache)

    a1, _ = await worker_a.anonymize("Bonjour Patrick", thread_id="t")
    # worker_b never saw message 1; it must hydrate memory from the cache.
    a2, _ = await worker_b.anonymize("Alice est la", thread_id="t")
    assert a1 == "Bonjour <<PERSON:1>>"
    assert a2 == "<<PERSON:2>> est la"

    # And worker_a must learn about Alice for deanonymization.
    restored = await worker_a.deanonymize_with_ent("<<PERSON:2>>", thread_id="t")
    assert restored == "Alice"


async def test_threads_stay_isolated():
    pipe = _pipeline()
    a1, _ = await pipe.anonymize("Bonjour Patrick", thread_id="t1")
    a2, _ = await pipe.anonymize("Alice est la", thread_id="t2")
    # Separate threads each start their own numbering.
    assert a1 == "Bonjour <<PERSON:1>>"
    assert a2 == "<<PERSON:1>> est la"
