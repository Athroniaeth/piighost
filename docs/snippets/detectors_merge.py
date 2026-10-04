import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import RegexDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline

# isort: split
# --8<-- [start:example]
from piighost.hub import pull

patterns = {**pull("hub:piighost/generic"), **pull("hub:piighost/fr")}
detector = RegexDetector(patterns)

linker = ExactEntityLinker()
factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
pipeline = AnonymizationPipeline(
    detector,
    linker,
    anonymizer,
)


async def main():
    result = await pipeline.anonymize(
        "IBAN FR7630006000011234567890189, email marie@exemple.fr, tel 06 12 34 56 78."
    )
    print(result.text)
    # IBAN <<FR_IBAN:1>>, email <<EMAIL:1>>, tel <<FR_PHONE:1>>.


asyncio.run(main())
# --8<-- [end:example]
