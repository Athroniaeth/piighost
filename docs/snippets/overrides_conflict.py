import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.override import DetectionOverride, OverrideConflictStrategy
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.exceptions import ConflictingOverrideError
from piighost.pipeline import AnonymizationPipeline


def build_pipeline(strategy: OverrideConflictStrategy) -> AnonymizationPipeline:
    detector = ExactMatchDetector({"Emma": "PERSON"})
    whitelist = ExactMatchDetector({"Acme": "ORG"})
    blacklist = ExactMatchDetector({"Acme": "ORG"})
    override = DetectionOverride(
        whitelist=whitelist,
        blacklist=blacklist,
        conflict_strategy=strategy,
    )
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
    for strategy in OverrideConflictStrategy:
        pipeline = build_pipeline(strategy)
        try:
            result = await pipeline.anonymize("Emma works at Acme.")
        except ConflictingOverrideError as error:
            print(strategy.value, "->", type(error).__name__, error)
        else:
            print(strategy.value, "->", result.text)


asyncio.run(main())
