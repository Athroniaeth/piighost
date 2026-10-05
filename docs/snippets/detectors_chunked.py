import asyncio

from piighost.pipeline import AnonymizationPipeline

# isort: split
# --8<-- [start:example]
from piighost.components.detector import ChunkedDetector, RegexDetector
from piighost.text import RecursiveCharacterTextSplitter

regex_detector = RegexDetector.from_catalog("catalog:piighost/generic")
splitter = RecursiveCharacterTextSplitter(chunk_size=40, chunk_overlap=10)
detector = ChunkedDetector(regex_detector, splitter=splitter)
pipeline = AnonymizationPipeline(detector)


async def main() -> None:
    text = (
        "Filler text here. Reach alice@example.com now. "
        "More filler padding words. Then bob@example.org later."
    )
    result = await pipeline.anonymize(text)
    print(result.text)


asyncio.run(main())
# --8<-- [end:example]
