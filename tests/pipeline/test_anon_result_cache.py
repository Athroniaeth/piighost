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
from piighost.models import Detection, Span
from piighost.observation.base import (
    AbstractObservationService,
    NoOpSpan,
)
from piighost.pipeline.base import (
    CACHE_KEY_ANON_RESULT,
    CACHE_KEY_DETECTION,
    AnonymizationPipeline,
)
from piighost.pipeline.thread import ThreadAnonymizationPipeline
from piighost.placeholder import LabelCounterPlaceholderFactory
from piighost.placeholder_tags import PreservesIdentity
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


class RecordingSpan(NoOpSpan):
    """Span whose ``update()`` calls are captured for assertions."""

    def __init__(self) -> None:
        self.updates: list[dict[str, Any]] = []

    def update(
        self,
        *,
        input: Any = None,
        output: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {}
        if input is not None:
            kwargs["input"] = input
        if output is not None:
            kwargs["output"] = output
        if metadata is not None:
            kwargs["metadata"] = metadata
        self.updates.append(kwargs)


class RecordingObservation(AbstractObservationService):
    """Observation service that records spans and their update history."""

    def __init__(self) -> None:
        self.spans: list[tuple[dict[str, Any], RecordingSpan]] = []

    @contextmanager
    def start_as_current_span(self, **kwargs: Any):
        span = RecordingSpan()
        self.spans.append((kwargs, span))
        yield span


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

    async def test_base_anonymize_with_root_span_uses_cache(self) -> None:
        """A cached result short-circuits even when a root_span is supplied."""
        calls = 0

        class CountingDetector:
            async def detect(self, text: str):
                nonlocal calls
                calls += 1
                return [
                    Detection(
                        text="Patrick",
                        label="PERSON",
                        position=Span(8, 15),
                        confidence=1.0,
                    )
                ]

        pipe = AnonymizationPipeline(
            detector=CountingDetector(), anonymizer=Anonymizer()
        )
        first, _ = await pipe.anonymize("Bonjour Patrick")
        second, _ = await pipe.anonymize("Bonjour Patrick", root_span=NoOpSpan())
        assert first == second
        assert calls == 1

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
        ThreadAnonymizationPipeline[PreservesIdentity],
        CountingDetector,
        CountingObservation,
        SimpleMemoryCache,
    ]:
        cache = SimpleMemoryCache()
        observation = CountingObservation()
        detector = CountingDetector([("Patrick", "PERSON")])
        pipeline: ThreadAnonymizationPipeline[PreservesIdentity] = (
            ThreadAnonymizationPipeline(
                detector=detector,
                anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
                cache=cache,
                observation=observation,
            )
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

        # User corrects detections via HITL: declares no PII at all. This
        # opens its own observation span (piighost.hitl_correction) and
        # invalidates the anon-result cache.
        await pipeline.override_detections("Bonjour Patrick", [], thread_id="t1")
        assert observation.span_count == 2

        result2, ents = await pipeline.anonymize("Bonjour Patrick", thread_id="t1")
        # Third span: the anonymize re-ran because the anon-result cache
        # was invalidated by the override.
        assert observation.span_count == 3

    async def test_override_to_empty_drops_entity_from_memory(self) -> None:
        """HITL correction declaring no PII must stop re-anonymizing it.

        The thread pipeline renders from conversation memory, so dropping
        the detection cache is not enough: the entity recorded in memory
        must also be reconciled, otherwise the memory-wide render keeps
        replacing the corrected surface form.
        """
        pipeline, _, _, _ = self._build()

        result1, _ = await pipeline.anonymize("Bonjour Patrick", thread_id="t1")
        assert result1 == "Bonjour <<PERSON:1>>"

        # Human says: "Patrick" here is not PII -> empty corrected detections.
        await pipeline.override_detections("Bonjour Patrick", [], thread_id="t1")

        result2, ents = await pipeline.anonymize("Bonjour Patrick", thread_id="t1")
        assert result2 == "Bonjour Patrick"
        assert ents == []
        assert pipeline.get_memory("t1").all_entities == []

    async def test_override_preserves_entity_seen_in_another_message(self) -> None:
        """Correcting one message must not drop PII first seen elsewhere.

        Patrick is first recorded in message 1.  Correcting message 2 to
        drop its Patrick detection is a no-op on memory (Patrick lives in
        message 1's bucket), so message 1 stays anonymized.
        """
        pipeline, _, _, _ = self._build()

        await pipeline.anonymize("Bonjour Patrick", thread_id="t1")
        await pipeline.anonymize("Patrick encore", thread_id="t1")

        await pipeline.override_detections("Patrick encore", [], thread_id="t1")

        # Patrick was first seen in message 1, so it survives the correction.
        canonicals = [e.canonical for e in pipeline.get_memory("t1").all_entities]
        assert canonicals == ["patrick"]
        result, _ = await pipeline.anonymize("Bonjour Patrick", thread_id="t1")
        assert result == "Bonjour <<PERSON:1>>"

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

    async def test_deanonymize_with_ent_no_token_does_not_store(self) -> None:
        """A token-free text must not be cached as an anonymization (P3b).

        Memory is non-empty but the text carries no placeholder, so
        nothing is replaced and no clear-text mapping should be stored.
        """
        pipeline, _, _, _ = self._build()

        # Seed memory with an entity so token_map is non-empty.
        await pipeline.anonymize("Bonjour Patrick", thread_id="t1")

        clear = "Le ciel est bleu aujourd'hui."
        result = await pipeline.deanonymize_with_ent(clear, thread_id="t1")
        assert result == clear  # unchanged, still returned

        # Nothing was stored: a strict deanonymize must report a cache miss
        # rather than a spurious hit on clear text.
        with pytest.raises(CacheMissError):
            await pipeline.deanonymize(clear, thread_id="t1")

    async def test_deanonymize_populates_anon_result(self) -> None:
        pipeline, _, observation, _ = self._build()

        anonymized, _ = await pipeline.anonymize("Bonjour Patrick", thread_id="t1")
        assert observation.span_count == 1

        original, _ = await pipeline.deanonymize(anonymized, thread_id="t1")
        assert original == "Bonjour Patrick"

        # Re-anonymizing the original must not emit a new span.
        await pipeline.anonymize(original, thread_id="t1")
        assert observation.span_count == 1

    async def test_override_detections_emits_hitl_span_with_diff(self) -> None:
        cache = SimpleMemoryCache()
        observation = RecordingObservation()
        detector = CountingDetector([("Patrick", "PERSON")])
        pipeline = ThreadAnonymizationPipeline(
            detector=detector,
            anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
            cache=cache,
            observation=observation,
        )

        # Populate the detection cache under thread t1 with the model output.
        await pipeline.anonymize("Bonjour Patrick", thread_id="t1")

        corrected = [
            Detection(
                text="Patrick",
                label="ORG",
                position=Span(start_pos=8, end_pos=15),
                confidence=1.0,
            )
        ]
        await pipeline.override_detections("Bonjour Patrick", corrected, thread_id="t1")

        hitl = [
            (kw, span)
            for kw, span in observation.spans
            if kw.get("name") == "piighost.hitl_correction"
        ]
        assert len(hitl) == 1
        kw, span = hitl[0]
        assert kw.get("tags") == ["hitl"]
        assert kw.get("session_id") == "t1"
        assert len(span.updates) == 1
        update = span.updates[0]
        assert "input" in update and "output" in update
        # Model said PERSON, human said ORG.
        assert update["input"]["detections"][0]["label"] == "PERSON"
        assert update["output"]["detections"][0]["label"] == "ORG"
        # observation_ph_factory defaults to None now, so detection text
        # is the raw user input. The user-facing LabelCounterPlaceholderFactory
        # is unrelated to observation redaction.
        assert update["input"]["detections"][0]["text"] == "Patrick"
        assert update["output"]["detections"][0]["text"] == "Patrick"
        # Raw input text and the detector's label vocabulary land in
        # input.* so the trace doubles as a NER training record. The
        # ExactMatchDetector here exposes no `.labels`, so the field is
        # an empty list rather than ``None``.
        assert update["input"]["text"] == "Bonjour Patrick"
        assert update["input"]["labels"] == []

    async def test_override_detections_emits_span_with_empty_before(self) -> None:
        cache = SimpleMemoryCache()
        observation = RecordingObservation()
        detector = CountingDetector([("Patrick", "PERSON")])
        pipeline = ThreadAnonymizationPipeline(
            detector=detector,
            anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
            cache=cache,
            observation=observation,
        )

        corrected = [
            Detection(
                text="Patrick",
                label="PERSON",
                position=Span(start_pos=8, end_pos=15),
                confidence=1.0,
            )
        ]
        # No anonymize / detect call before override → cache empty.
        await pipeline.override_detections("Bonjour Patrick", corrected, thread_id="t1")

        hitl = [
            (kw, span)
            for kw, span in observation.spans
            if kw.get("name") == "piighost.hitl_correction"
        ]
        assert len(hitl) == 1
        kw, span = hitl[0]
        update = span.updates[0]
        assert update["input"]["detections"] == []
        assert len(update["output"]["detections"]) == 1
        assert update["output"]["detections"][0]["label"] == "PERSON"

    async def test_override_detections_swallows_observation_errors(self) -> None:
        class RaisingObservation(AbstractObservationService):
            @contextmanager
            def start_as_current_span(self, **kwargs: Any):
                raise RuntimeError("backend exploded")
                yield NoOpSpan()  # pragma: no cover - unreachable

        cache = SimpleMemoryCache()
        pipeline = ThreadAnonymizationPipeline(
            detector=ExactMatchDetector([("Patrick", "PERSON")]),
            anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
            cache=cache,
            observation=RaisingObservation(),
        )

        corrected = [
            Detection(
                text="Patrick",
                label="ORG",
                position=Span(start_pos=8, end_pos=15),
                confidence=1.0,
            )
        ]

        # Must not raise even though the observation backend explodes.
        await pipeline.override_detections("Bonjour Patrick", corrected, thread_id="t1")

        # Cache was still overwritten with the corrected detections.
        detect_key = f"t1:{CACHE_KEY_DETECTION}:{hash_sha256('Bonjour Patrick')}"
        cached = await cache.get(detect_key)
        assert cached is not None
        # Decoded value should reflect the corrected ORG label.
        assert any(item["label"] == "ORG" for item in cached)

    async def test_explicit_obs_factory_emits_config_warning(self) -> None:
        import warnings

        from piighost.exceptions import PIIGhostConfigWarning
        from piighost.placeholder import RedactPlaceholderFactory

        cache = SimpleMemoryCache()
        detector = ExactMatchDetector([("Patrick", "PERSON")])
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", PIIGhostConfigWarning)
            ThreadAnonymizationPipeline(
                detector=detector,
                anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
                cache=cache,
                observation_ph_factory=RedactPlaceholderFactory(),
            )
        relevant = [
            w
            for w in caught
            if issubclass(w.category, PIIGhostConfigWarning)
            and "observation_ph_factory" in str(w.message)
        ]
        assert len(relevant) == 1
        assert "observation_ph_factory" in str(relevant[0].message)
        assert "redacted" in str(relevant[0].message).lower()

    async def test_default_observation_keeps_raw_text(self) -> None:
        cache = SimpleMemoryCache()
        observation = RecordingObservation()
        detector = CountingDetector([("Patrick", "PERSON")])
        pipeline = ThreadAnonymizationPipeline(
            detector=detector,
            anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
            cache=cache,
            observation=observation,
            # observation_ph_factory omitted -> default None -> raw text
        )

        await pipeline.anonymize("Bonjour Patrick", thread_id="t1")

        anon = [
            (kw, span)
            for kw, span in observation.spans
            if kw.get("name") == "piighost.anonymize_pipeline"
        ]
        assert len(anon) == 1
        _, span = anon[0]
        raw_inputs = [u for u in span.updates if "input" in u]
        assert raw_inputs, "expected at least one input update on the root span"
        assert raw_inputs[0]["input"]["text"] == "Bonjour Patrick"

    async def test_override_detections_with_obs_factory_redacts(self) -> None:
        import warnings

        from piighost.exceptions import PIIGhostConfigWarning
        from piighost.placeholder import RedactPlaceholderFactory

        cache = SimpleMemoryCache()
        observation = RecordingObservation()
        detector = CountingDetector([("Patrick", "PERSON")])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", PIIGhostConfigWarning)
            pipeline = ThreadAnonymizationPipeline(
                detector=detector,
                anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
                cache=cache,
                observation=observation,
                observation_ph_factory=RedactPlaceholderFactory(),
            )

        await pipeline.anonymize("Bonjour Patrick", thread_id="t1")
        corrected = [
            Detection(
                text="Patrick",
                label="ORG",
                position=Span(start_pos=8, end_pos=15),
                confidence=1.0,
            )
        ]
        await pipeline.override_detections("Bonjour Patrick", corrected, thread_id="t1")

        hitl = [
            (kw, span)
            for kw, span in observation.spans
            if kw.get("name") == "piighost.hitl_correction"
        ]
        assert len(hitl) == 1
        _, span = hitl[0]
        update = span.updates[0]
        # input.text stays raw (same as before): the HITL trace always
        # carries the raw text so the dataset stays extractable. But
        # detection.text is redacted because the explicit factory is set.
        assert update["input"]["text"] == "Bonjour Patrick"
        assert update["input"]["detections"][0]["text"] != "Patrick"
        assert update["output"]["detections"][0]["text"] != "Patrick"

    async def test_override_detections_no_op_observation_keeps_contract(
        self,
    ) -> None:
        cache = SimpleMemoryCache()
        pipeline = ThreadAnonymizationPipeline(
            detector=ExactMatchDetector([("Patrick", "PERSON")]),
            anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
            cache=cache,
            # observation omitted → NoOpObservationService default
        )

        corrected = [
            Detection(
                text="Patrick",
                label="PERSON",
                position=Span(start_pos=8, end_pos=15),
                confidence=1.0,
            )
        ]
        await pipeline.override_detections("Bonjour Patrick", corrected, thread_id="t1")

        detect_key = f"t1:{CACHE_KEY_DETECTION}:{hash_sha256('Bonjour Patrick')}"
        cached = await cache.get(detect_key)
        assert cached is not None
        assert any(item["label"] == "PERSON" for item in cached)


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
