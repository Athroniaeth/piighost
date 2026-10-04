import asyncio

from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import AnonymizationPipeline

detector = ExactMatchDetector({"John Doe": "PERSON", "Paris": "LOCATION"})
pipeline = AnonymizationPipeline(detector)


async def main() -> None:
    result = await pipeline.anonymize("John Doe lives in Paris.")
    assert result.text == "<<PERSON:1>> lives in <<LOCATION:1>>."


asyncio.run(main())
