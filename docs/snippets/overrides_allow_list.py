import asyncio

from piighost.components.detector import ExactMatchDetector
from piighost.components.override import DetectionOverride
from piighost.pipeline import AnonymizationPipeline

detector = ExactMatchDetector({"Emma": "PERSON", "Acme": "ORG"})
allow_list = ExactMatchDetector({"Acme": "ORG"})
override = DetectionOverride(allow_list=allow_list)
pipeline = AnonymizationPipeline(detector, override=override)


async def main() -> None:
    result = await pipeline.anonymize("Emma works at Acme.")
    print(result.text)


asyncio.run(main())
