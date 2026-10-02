import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.linker import ExactEntityLinker
from piighost.components.override import DetectionOverride
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline

# isort: split
# --8<-- [start:example]
from piighost.components.detector import ExactMatchDetector

detector = ExactMatchDetector({"Emma": "PERSON", "Acme": "PERSON"})
whitelist = ExactMatchDetector({"Acme": "ORG"})
override = DetectionOverride(whitelist=whitelist)
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
    result = await pipeline.anonymize("Acme hired Emma.")
    print(result.text)
    # <<ORG:1>> hired <<PERSON:1>>.


asyncio.run(main())
# --8<-- [end:example]
