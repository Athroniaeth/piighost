import asyncio

from piighost.components.detector import ExactMatchDetector
from piighost.components.override import DetectionOverride, OverrideConflictStrategy
from piighost.exceptions import ConflictingOverrideError
from piighost.pipeline import AnonymizationPipeline


def build_pipeline(strategy: OverrideConflictStrategy) -> AnonymizationPipeline:
    detector = ExactMatchDetector({"Emma": "PERSON"})
    deny_list = ExactMatchDetector({"Acme": "ORG"})
    allow_list = ExactMatchDetector({"Acme": "ORG"})
    override = DetectionOverride(
        deny_list=deny_list,
        allow_list=allow_list,
        conflict_strategy=strategy,
    )
    return AnonymizationPipeline(detector, override=override)


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
