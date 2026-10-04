import asyncio

from piighost.components.detector import ExactMatchDetector
from piighost.components.override import DetectionOverride
from piighost.pipeline import AnonymizationPipeline

detector = ExactMatchDetector({"Emma": "PERSON", "Acme": "ORG"})
blacklist = ExactMatchDetector({"Acme": "ORG"})
override = DetectionOverride(blacklist=blacklist)
pipeline = AnonymizationPipeline(detector, override=override)


async def main():
    result = await pipeline.anonymize("Emma works at Acme.")
    print(result.text)
    # <<PERSON:1>> works at Acme.


asyncio.run(main())
