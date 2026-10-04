import asyncio

from piighost.pipeline import AnonymizationPipeline

# isort: split
# --8<-- [start:exact]
from piighost.components.detector import ExactMatchDetector

detector = ExactMatchDetector({"Patrick": "PERSON", "Paris": "LOCATION"})
pipeline = AnonymizationPipeline(detector)


async def main() -> None:
    result = await pipeline.anonymize("Patrick habite à Paris. Patrick aime Paris.")
    print(result.text)


asyncio.run(main())
# --8<-- [end:exact]
