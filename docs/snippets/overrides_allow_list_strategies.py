import asyncio

from piighost.components.detector import ExactMatchDetector
from piighost.components.override import AllowListStrategy, DetectionOverride
from piighost.pipeline import AnonymizationPipeline


def build_pipeline(strategy: AllowListStrategy) -> AnonymizationPipeline:
    detector = ExactMatchDetector(
        {"Emma": "PERSON", "Acme": "PERSON", "Globex Ltd": "ORG"}
    )
    allow_list = ExactMatchDetector({"Acme": "ORG", "Globex": "ORG"})
    override = DetectionOverride(allow_list=allow_list, allow_list_strategy=strategy)
    return AnonymizationPipeline(detector, override=override)


async def main():
    text = "Emma works at Acme, formerly Globex Ltd."
    for strategy in AllowListStrategy:
        pipeline = build_pipeline(strategy)
        result = await pipeline.anonymize(text)
        print(strategy.value, "->", result.text)


asyncio.run(main())
