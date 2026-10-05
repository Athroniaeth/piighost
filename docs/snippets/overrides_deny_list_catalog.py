import asyncio

from piighost.components.detector import RegexDetector
from piighost.components.override import DetectionOverride
from piighost.pipeline import AnonymizationPipeline

detector = RegexDetector.from_catalog("catalog:piighost/generic")
deny_list = RegexDetector({"CODENAME": r"ACME-[A-Z]+"})
override = DetectionOverride(deny_list=deny_list)
pipeline = AnonymizationPipeline(detector, override=override)


async def main() -> None:
    result = await pipeline.anonymize("Ship ACME-FALCON to alice@example.com.")
    print(result.text)


asyncio.run(main())
