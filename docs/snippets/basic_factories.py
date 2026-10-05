# --8<-- [start:factories]
import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.placeholder import LabelHashPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline

detector = ExactMatchDetector({"Patrick": "PERSON", "Marie": "PERSON"})
anonymizer = Anonymizer(LabelHashPlaceholderFactory())
pipeline = AnonymizationPipeline(detector, anonymizer=anonymizer)


async def main() -> None:
    result = await pipeline.anonymize("Patrick, Marie, Patrick.")
    print(result.text)


asyncio.run(main())
# --8<-- [end:factories]
