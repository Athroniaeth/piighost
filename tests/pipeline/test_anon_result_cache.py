"""Tests for the anonymize-result cache (CACHE_KEY_ANON_RESULT).

The cache short-circuits ``pipeline.anonymize`` when the mapping for
*text* is already known, skipping both the pipeline run and the
observation root span. It is populated on every successful ``anonymize``
and on every ``deanonymize`` (where both forms become known), and is
invalidated by ``override_detections``.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest
from aiocache import SimpleMemoryCache

from piighost.anonymizer import Anonymizer
from piighost.detector import ExactMatchDetector
from piighost.exceptions import CacheMissError
from piighost.observation.base import (
    AbstractObservationService,
    NoOpSpan,
)
from piighost.pipeline.base import (
    CACHE_KEY_ANON_RESULT,
    AnonymizationPipeline,
)
from piighost.pipeline.thread import ThreadAnonymizationPipeline
from piighost.placeholder import LabelCounterPlaceholderFactory
from piighost.utils import hash_sha256


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class CountingObservation(AbstractObservationService):
    """Observation service that counts root-span openings."""

    def __init__(self) -> None:
        self.span_count = 0

    @contextmanager
    def start_as_current_span(self, **kwargs: Any):
        self.span_count += 1
        yield NoOpSpan()


class CountingDetector(ExactMatchDetector):
    """Detector that records its detect-call count."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.call_count = 0

    async def detect(self, text: str):
        self.call_count += 1
        return await super().detect(text)


# ---------------------------------------------------------------------------
# Base AnonymizationPipeline
# ---------------------------------------------------------------------------


class TestAnonResultCacheBase:
    """Cache behaviour on the base (non-thread) pipeline."""

    async def test_second_anonymize_skips_pipeline_and_span(self) -> None:
        cache = SimpleMemoryCache()
        observation = CountingObservation()
        detector = CountingDetector([("Patrick", "PERSON")])
        pipeline = AnonymizationPipeline(
            detector=detector,
            anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
            cache=cache,
            observation=observation,
        )

        result1, _ = await pipeline.anonymize("Bonjour Patrick")
        assert result1 == "Bonjour <<PERSON:1>>"
        assert observation.span_count == 1
        assert detector.call_count == 1

        result2, ents = await pipeline.anonymize("Bonjour Patrick")
        assert result2 == "Bonjour <<PERSON:1>>"
        # Same number of spans + detector calls: cache hit fully bypassed
        # the pipeline and the observation root span.
        assert observation.span_count == 1
        assert detector.call_count == 1
        assert len(ents) == 1

    async def test_deanonymize_populates_anon_result_cache(self) -> None:
        cache = SimpleMemoryCache()
        observation = CountingObservation()
        detector = CountingDetector([("Patrick", "PERSON")])
        pipeline = AnonymizationPipeline(
            detector=detector,
            anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
            cache=cache,
            observation=observation,
        )

        anonymized, _ = await pipeline.anonymize("Bonjour Patrick")
        assert observation.span_count == 1

        # ``deanonymize`` is the moment we know both forms; it must
        # populate the inverse cache.
        original, _ = await pipeline.deanonymize(anonymized)
        assert original == "Bonjour Patrick"

        # Now anonymize the *original* — should hit the cache populated
        # by deanonymize, not run the pipeline again.
        before_count = observation.span_count
        await pipeline.anonymize(original)
        assert observation.span_count == before_count

    async def test_cache_uses_anon_result_prefix(self) -> None:
        cache = SimpleMemoryCache()
        pipeline = AnonymizationPipeline(
            detector=ExactMatchDetector([("Patrick", "PERSON")]),
            anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
            cache=cache,
        )

        await pipeline.anonymize("Bonjour Patrick")

        expected_key = f"{CACHE_KEY_ANON_RESULT}:{hash_sha256('Bonjour Patrick')}"
        cached = await cache.get(expected_key)
        assert cached is not None
        assert cached["anonymized"] == "Bonjour <<PERSON:1>>"


# ---------------------------------------------------------------------------
# Thread pipeline
# ---------------------------------------------------------------------------


class TestAnonResultCacheThread:
    """Cache behaviour on the conversation-aware pipeline."""

    def _build(
        self,
    ) -> tuple[
        ThreadAnonymizationPipeline,
        CountingDetector,
        CountingObservation,
        SimpleMemoryCache,
    ]:
        cache = SimpleMemoryCache()
        observation = CountingObservation()
        detector = CountingDetector([("Patrick", "PERSON")])
        pipeline = ThreadAnonymizationPipeline(
            detector=detector,
            anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
            cache=cache,
            observation=observation,
        )
        return pipeline, detector, observation, cache

    async def test_second_anonymize_skips_span(self) -> None:
        pipeline, detector, observation, _ = self._build()

        await pipeline.anonymize("Bonjour Patrick", thread_id="t1")
        assert observation.span_count == 1

        await pipeline.anonymize("Bonjour Patrick", thread_id="t1")
        assert observation.span_count == 1
        assert detector.call_count == 1

    async def test_cache_is_thread_isolated(self) -> None:
        pipeline, _, observation, _ = self._build()

        await pipeline.anonymize("Bonjour Patrick", thread_id="t1")
        assert observation.span_count == 1

        # Different thread id → cache miss → pipeline runs → new span.
        await pipeline.anonymize("Bonjour Patrick", thread_id="t2")
        assert observation.span_count == 2

    async def test_override_detections_invalidates_anon_result(self) -> None:
        pipeline, _, observation, _ = self._build()

        # First call populates both detect cache and anon-result cache.
        result1, _ = await pipeline.anonymize("Bonjour Patrick", thread_id="t1")
        assert "<<PERSON:1>>" in result1
        assert observation.span_count == 1

        # User corrects detections via HITL: declares no PII at all.
        # If the anon-result cache is NOT invalidated, the next anonymize
        # would return the stale pre-correction result.
        await pipeline.override_detections("Bonjour Patrick", [], thread_id="t1")

        result2, ents = await pipeline.anonymize("Bonjour Patrick", thread_id="t1")
        # Span count went up → pipeline re-ran → cache was invalidated.
        assert observation.span_count == 2

    async def test_deanonymize_with_ent_populates_anon_result(self) -> None:
        pipeline, _, observation, _ = self._build()

        anonymized, _ = await pipeline.anonymize("Bonjour Patrick", thread_id="t1")
        assert observation.span_count == 1

        # Simulate the middleware ``aafter_model`` flow: an LLM-generated
        # message containing the placeholder is fed through
        # ``deanonymize_with_ent``. This populates the anon-result cache
        # for the deanonymized form so the next ``abefore_model`` finds it.
        ai_text = f"Hi {anonymized.split()[1]}!"  # "Hi <<PERSON:1>>!"
        deanon = await pipeline.deanonymize_with_ent(ai_text, thread_id="t1")
        assert deanon == "Hi Patrick!"

        # Now ``anonymize`` of the deanonymized form should hit the cache
        # and skip the span.
        before = observation.span_count
        result, _ = await pipeline.anonymize("Hi Patrick!", thread_id="t1")
        assert observation.span_count == before
        assert "<<PERSON:1>>" in result

    async def test_deanonymize_populates_anon_result(self) -> None:
        pipeline, _, observation, _ = self._build()

        anonymized, _ = await pipeline.anonymize("Bonjour Patrick", thread_id="t1")
        assert observation.span_count == 1

        original, _ = await pipeline.deanonymize(anonymized, thread_id="t1")
        assert original == "Bonjour Patrick"

        # Re-anonymizing the original must not emit a new span.
        await pipeline.anonymize(original, thread_id="t1")
        assert observation.span_count == 1


# ---------------------------------------------------------------------------
# Base.deanonymize CacheMissError unchanged
# ---------------------------------------------------------------------------


class TestDeanonymizeUnknown:
    async def test_base_deanonymize_unknown_still_raises(self) -> None:
        cache = SimpleMemoryCache()
        pipeline = AnonymizationPipeline(
            detector=ExactMatchDetector([("Patrick", "PERSON")]),
            anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
            cache=cache,
        )

        with pytest.raises(CacheMissError):
            await pipeline.deanonymize("never seen text")
