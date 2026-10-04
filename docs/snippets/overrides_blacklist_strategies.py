import asyncio

from piighost.components.detector import ExactMatchDetector
from piighost.components.override import BlacklistStrategy, DetectionOverride
from piighost.pipeline import AnonymizationPipeline


def build_pipeline(strategy: BlacklistStrategy) -> AnonymizationPipeline:
    detector = ExactMatchDetector(
        {"Emma": "PERSON", "Acme": "PERSON", "Globex Ltd": "ORG"}
    )
    blacklist = ExactMatchDetector({"Acme": "ORG", "Globex": "ORG"})
    override = DetectionOverride(blacklist=blacklist, blacklist_strategy=strategy)
    return AnonymizationPipeline(detector, override=override)


async def main():
    text = "Emma works at Acme, formerly Globex Ltd."
    for strategy in BlacklistStrategy:
        pipeline = build_pipeline(strategy)
        result = await pipeline.anonymize(text)
        print(strategy.value, "->", result.text)


asyncio.run(main())
