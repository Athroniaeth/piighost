import asyncio

from piighost.components.detector import RegexDetector
from piighost.pipeline import AnonymizationPipeline

detector = RegexDetector.from_hub("hub:piighost/generic")
pipeline = AnonymizationPipeline(detector)


async def main():
    result = await pipeline.anonymize("Email alice@example.com, server 192.168.1.42.")
    print(result.text)
    # Email <<EMAIL:1>>, server <<IPV4:1>>.


asyncio.run(main())
