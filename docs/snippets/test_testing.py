# --8<-- [start:helper]
from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline


def build_pipeline(values: dict[str, str]) -> AnonymizationPipeline:
    detector = ExactMatchDetector(values)
    linker = ExactEntityLinker()
    factory = LabelCounterPlaceholderFactory()
    anonymizer = Anonymizer(factory)
    return AnonymizationPipeline(
        detector,
        linker,
        anonymizer,
    )


async def test_person_is_tokenized() -> None:
    """A detected person becomes its token, and the raw value is gone."""
    pipeline = build_pipeline({"Alice": "PERSON"})
    result = await pipeline.anonymize("Alice lives in Lyon.")
    assert result.text == "<<PERSON:1>> lives in Lyon."
    assert "Alice" not in result.text


# --8<-- [end:helper]


# --8<-- [start:repeat]
async def test_repeat_shares_one_token() -> None:
    """A repeated value reuses its first token."""
    pipeline = build_pipeline({"Alice": "PERSON"})
    result = await pipeline.anonymize("Alice met Alice again.")
    assert result.text == "<<PERSON:1>> met <<PERSON:1>> again."


# --8<-- [end:repeat]
