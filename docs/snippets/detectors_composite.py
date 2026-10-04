import asyncio

from piighost.pipeline import AnonymizationPipeline

# isort: split
# --8<-- [start:example]
from piighost.components.detector import (
    CompositeDetector,
    ExactMatchDetector,
    RegexDetector,
)

exact_detector = ExactMatchDetector({"Patrick": "PERSON"})
regex_detector = RegexDetector.from_hub("hub:piighost/generic")
detector = CompositeDetector([exact_detector, regex_detector])
pipeline = AnonymizationPipeline(detector)


async def main() -> None:
    result = await pipeline.anonymize("Patrick emailed alice@example.com.")
    print(result.text)


asyncio.run(main())
# --8<-- [end:example]
