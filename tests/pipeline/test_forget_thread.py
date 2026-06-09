"""forget_thread must erase memory and every cache entry of the thread."""

import asyncio

import pytest
from aiocache import SimpleMemoryCache

from piighost.anonymizer import Anonymizer
from piighost.detector.base import ExactMatchDetector
from piighost.exceptions import CacheMissError
from piighost.pipeline.base import DEFAULT_CACHE_TTL
from piighost.pipeline.thread import ThreadAnonymizationPipeline


def _pipeline(cache=None) -> ThreadAnonymizationPipeline:
    return ThreadAnonymizationPipeline(
        detector=ExactMatchDetector([("Patrick", "PERSON")]),
        anonymizer=Anonymizer(),
        cache=cache,
    )


class LatentCache(SimpleMemoryCache):
    """SimpleMemoryCache whose get/set yield to the event loop, exposing RMW races."""

    async def _get(self, key, encoding="utf-8", _conn=None):
        await asyncio.sleep(0)
        return await super()._get(key, encoding=encoding, _conn=_conn)

    async def _set(self, key, value, ttl=None, _cas_token=None, _conn=None):
        await asyncio.sleep(0)
        return await super()._set(
            key, value, ttl=ttl, _cas_token=_cas_token, _conn=_conn
        )


async def test_concurrent_writes_do_not_orphan_keys():
    """Concurrent anonymize calls on one thread must leave no key unindexed."""
    cache = LatentCache()
    pipe = _pipeline(cache)
    texts = [f"Bonjour Patrick numero {i}" for i in range(20)]
    await asyncio.gather(*(pipe.anonymize(t, thread_id="t") for t in texts))
    await pipe.forget_thread("t")
    leftover = [k for k in cache._cache.keys() if str(k).startswith("t:")]
    assert leftover == []


async def test_forget_thread_concurrent_with_anonymize_leaves_no_orphans():
    """A purge racing in-flight anonymize calls must not orphan cache keys.

    The anonymize calls may legitimately re-create entries after the purge
    (they can be past the index read when forget_thread runs), but every
    surviving key must stay INDEXED so a later quiescent forget_thread
    finds and removes all of them.  Before forget_thread took the
    per-thread lock (and stopped popping it, which minted a fresh lock for
    in-flight writers and let two index RMWs interleave), specific
    schedulings left ``t:detect:*`` keys behind for good.  Sweep the
    forget offset to cover those interleavings.
    """
    for delay in range(30):
        cache = LatentCache()
        pipe = _pipeline(cache)

        async def delayed_forget(ticks: int = delay) -> None:
            for _ in range(ticks):
                await asyncio.sleep(0)
            await pipe.forget_thread("t")  # noqa: B023

        await asyncio.gather(
            pipe.anonymize("Bonjour Patrick", thread_id="t"),
            pipe.anonymize("Salut Patrick", thread_id="t"),
            delayed_forget(),
        )
        # Quiescent purge: everything the racing anonymize calls wrote
        # must be discoverable through the index and erased.
        await pipe.forget_thread("t")
        leftover = [k for k in cache._cache.keys() if str(k).startswith("t:")]
        assert leftover == [], f"orphaned keys at forget offset {delay}: {leftover}"


async def test_snapshot_republished_after_expiry():
    """A worker holding RAM memory must re-publish the snapshot if it expired."""
    cache = SimpleMemoryCache()
    pipe = _pipeline(cache)
    await pipe.anonymize("Bonjour Patrick", thread_id="t")
    # Simulate backend expiry of the snapshot only.
    await cache.delete(pipe._memory_key("t"))
    # Same text again: nothing new is recorded, but the snapshot must come back.
    await pipe.anonymize("Bonjour Patrick", thread_id="t")
    assert await cache.get(pipe._memory_key("t")) is not None


def test_default_ttl_is_one_hour():
    assert DEFAULT_CACHE_TTL == 3600
    pipe = _pipeline()
    assert pipe._cache_ttl == 3600


async def test_forget_thread_erases_cache_and_memory():
    cache = SimpleMemoryCache()
    pipe = _pipeline(cache)
    anonymized, _ = await pipe.anonymize("Bonjour Patrick", thread_id="t")

    await pipe.forget_thread("t")

    # Memory gone: nothing left to replace.
    assert pipe.anonymize_with_ent("Patrick", thread_id="t") == "Patrick"
    # Mappings gone: deanonymize misses.
    with pytest.raises(CacheMissError):
        await pipe.deanonymize(anonymized, thread_id="t")
    # No stray thread-scoped keys survive in the backend.
    leftover = [k for k in cache._cache.keys() if str(k).startswith("t:")]
    assert leftover == []


async def test_forget_thread_does_not_touch_other_threads():
    pipe = _pipeline()
    await pipe.anonymize("Bonjour Patrick", thread_id="keep")
    await pipe.anonymize("Bonjour Patrick", thread_id="drop")
    await pipe.forget_thread("drop")
    assert pipe.anonymize_with_ent("Patrick", thread_id="keep") == "<<PERSON:1>>"


async def test_forget_thread_is_idempotent():
    pipe = _pipeline()
    await pipe.anonymize("Bonjour Patrick", thread_id="t")
    await pipe.forget_thread("t")
    # Forgetting an unknown / already-forgotten thread must not raise.
    await pipe.forget_thread("t")
    await pipe.forget_thread("never-seen")


async def test_forget_thread_survives_stale_snapshot_hydration():
    """A deanonymize/anonymize after forget must not resurrect entities."""
    cache = SimpleMemoryCache()
    pipe = _pipeline(cache)
    anonymized, _ = await pipe.anonymize("Bonjour Patrick", thread_id="t")
    await pipe.forget_thread("t")

    # The mapping is gone immediately after forget.
    with pytest.raises(CacheMissError):
        await pipe.deanonymize(anonymized, thread_id="t")

    # Hydration runs at the top of anonymize; the snapshot key was
    # deleted, so a fresh call renumbers from scratch rather than
    # resurrecting the forgotten entity at a stale counter value.
    again, _ = await pipe.anonymize("Salut Patrick et Marie", thread_id="t")
    assert again == "Salut <<PERSON:1>> et Marie"


async def test_snapshot_and_entries_share_ttl():
    """The memory snapshot expires on the same TTL as the data entries."""
    cache = SimpleMemoryCache()
    pipe = ThreadAnonymizationPipeline(
        detector=ExactMatchDetector([("Patrick", "PERSON")]),
        anonymizer=Anonymizer(),
        cache=cache,
        cache_ttl=1,
    )
    await pipe.anonymize("Bonjour Patrick", thread_id="t")
    assert await cache.get(pipe._memory_key("t")) is not None

    await asyncio.sleep(1.1)

    # Snapshot expired on the shared TTL.
    assert await cache.get(pipe._memory_key("t")) is None
    # A fresh worker (no RAM memory) renumbers from 1: the snapshot is gone.
    fresh = ThreadAnonymizationPipeline(
        detector=ExactMatchDetector([("Patrick", "PERSON")]),
        anonymizer=Anonymizer(),
        cache=cache,
    )
    again, _ = await fresh.anonymize("Salut Patrick", thread_id="t")
    assert again == "Salut <<PERSON:1>>"
