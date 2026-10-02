import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline

# isort: split
# --8<-- [start:example]
from piighost.components.detector import (
    CompositeDetector,
    ExactMatchDetector,
    RegexDetector,
)

exact_detector = ExactMatchDetector({"Patrick": "PERSON"})
regex_detector = RegexDetector.from_hub("hub:piighost/generic:fab51b33")
detector = CompositeDetector([exact_detector, regex_detector])

linker = ExactEntityLinker()
factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
pipeline = AnonymizationPipeline(
    detector,
    linker,
    anonymizer,
)


async def main():
    result = await pipeline.anonymize("Patrick emailed alice@example.com.")
    print(result.text)
    # <<PERSON:1>> emailed <<EMAIL:1>>.


asyncio.run(main())
# --8<-- [end:example]
