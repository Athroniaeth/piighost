import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.override import DetectionOverride
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline

detector = ExactMatchDetector({"Emma": "PERSON", "Acme": "ORG"})
blacklist = ExactMatchDetector({"Acme": "ORG"})
override = DetectionOverride(blacklist=blacklist)
linker = ExactEntityLinker()
factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
pipeline = AnonymizationPipeline(
    detector,
    linker,
    anonymizer,
    override=override,
)


async def main():
    result = await pipeline.anonymize("Emma works at Acme.")
    print(result.text)
    # <<PERSON:1>> works at Acme.


asyncio.run(main())
