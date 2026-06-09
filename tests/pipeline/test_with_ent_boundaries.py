"""Word-boundary behaviour of anonymize_with_ent / deanonymize_with_ent."""

from piighost.anonymizer import Anonymizer
from piighost.detector.base import ExactMatchDetector
from piighost.pipeline.thread import ThreadAnonymizationPipeline


def _pipeline(*names: str) -> ThreadAnonymizationPipeline:
    detector = ExactMatchDetector([(n, "PERSON") for n in names])
    return ThreadAnonymizationPipeline(detector=detector, anonymizer=Anonymizer())


async def test_anonymize_with_ent_does_not_replace_inside_words():
    pipe = _pipeline("Ali")
    await pipe.anonymize("Ali est venu", thread_id="t")
    out = pipe.anonymize_with_ent("Alibaba et Ali", thread_id="t")
    assert out == "Alibaba et <<PERSON:1>>"


async def test_deanonymize_with_ent_replaces_token_glued_to_word():
    pipe = _pipeline("Patrick")
    await pipe.anonymize("Bonjour Patrick", thread_id="t")
    # LLM output may glue a token to a word; token replacement must not
    # require word boundaries (the << >> delimiters already isolate it).
    out = await pipe.deanonymize_with_ent("Bonjour<<PERSON:1>>!", thread_id="t")
    assert out == "BonjourPatrick!"
