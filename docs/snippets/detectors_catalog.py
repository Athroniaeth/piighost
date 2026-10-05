import asyncio

from piighost.components.detector import RegexDetector
from piighost.pipeline import AnonymizationPipeline

detector = RegexDetector.from_catalog("catalog:piighost/generic")
pipeline = AnonymizationPipeline(detector)


async def main() -> None:
    result = await pipeline.anonymize("Email alice@example.com, server 192.168.1.42.")
    print(result.text)


asyncio.run(main())
