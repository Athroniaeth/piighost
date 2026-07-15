"""Public APIs consumed by piighost-api (replacing private-attribute access)."""

from piighost.anonymizer import Anonymizer
from piighost.detector.base import ExactMatchDetector
from piighost.observation.base import NoOpObservationService
from piighost.pipeline.thread import ThreadAnonymizationPipeline


def _pipeline() -> ThreadAnonymizationPipeline:
    return ThreadAnonymizationPipeline(
        detector=ExactMatchDetector([("Patrick", "PERSON")]),
        anonymizer=Anonymizer(),
    )


async def test_detect_entities_accepts_thread_id():
    pipe = _pipeline()
    entities = await pipe.detect_entities("Bonjour Patrick", thread_id="t1")
    assert len(entities) == 1
    # The detection result must be cached under the t1 bucket, not "default":
    # override the detections for t1 and re-detect.
    await pipe.override_detections("Bonjour Patrick", [], thread_id="t1")
    assert await pipe.detect_entities("Bonjour Patrick", thread_id="t1") == []
    # Another thread is unaffected (fresh detector run).
    assert len(await pipe.detect_entities("Bonjour Patrick", thread_id="t2")) == 1


async def test_get_resolved_tokens_matches_anonymized_output():
    pipe = _pipeline()
    anonymized, _ = await pipe.anonymize("Bonjour Patrick", thread_id="t")
    assert anonymized == "Bonjour <<PERSON:1>>"
    tokens = pipe.get_resolved_tokens("t")
    assert list(tokens.values()) == ["<<PERSON:1>>"]
    entity = next(iter(tokens))
    assert entity.canonical == "patrick"


def test_observation_property_is_real_and_settable():
    from piighost.pipeline.base import AnonymizationPipeline

    assert isinstance(AnonymizationPipeline.__dict__["observation"], property)
    svc = NoOpObservationService()
    pipe = _pipeline()
    pipe.observation = svc
    assert pipe.observation is svc
    assert pipe._observation is svc
