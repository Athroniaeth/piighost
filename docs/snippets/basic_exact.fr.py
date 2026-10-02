import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline

# isort: split
# --8<-- [start:exact]
from piighost.components.detector import ExactMatchDetector

detector = ExactMatchDetector({"Patrick": "PERSON", "Paris": "LOCATION"})
linker = ExactEntityLinker()
factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
pipeline = AnonymizationPipeline(
    detector,
    linker,
    anonymizer,
)


async def main():
    result = await pipeline.anonymize("Patrick habite à Paris. Patrick aime Paris.")
    print(result.text)
    # <<PERSON:1>> habite à <<LOCATION:1>>. <<PERSON:1>> aime <<LOCATION:1>>.


asyncio.run(main())
# --8<-- [end:exact]
