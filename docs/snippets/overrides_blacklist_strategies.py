import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.override import BlacklistStrategy, DetectionOverride
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline


def build_pipeline(strategy: BlacklistStrategy) -> AnonymizationPipeline:
    detector = ExactMatchDetector(
        {"Emma": "PERSON", "Acme": "PERSON", "Globex Ltd": "ORG"}
    )
    blacklist = ExactMatchDetector({"Acme": "ORG", "Globex": "ORG"})
    override = DetectionOverride(blacklist=blacklist, blacklist_strategy=strategy)
    linker = ExactEntityLinker()
    factory = LabelCounterPlaceholderFactory()
    anonymizer = Anonymizer(factory)
    return AnonymizationPipeline(
        detector,
        linker,
        anonymizer,
        override=override,
    )


async def main():
    text = "Emma works at Acme, formerly Globex Ltd."
    for strategy in BlacklistStrategy:
        pipeline = build_pipeline(strategy)
        result = await pipeline.anonymize(text)
        print(strategy.value, "->", result.text)


asyncio.run(main())
