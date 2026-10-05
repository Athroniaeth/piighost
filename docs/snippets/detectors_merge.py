import asyncio

from piighost.components.detector import RegexDetector
from piighost.pipeline import AnonymizationPipeline

# isort: split
# --8<-- [start:example]
from piighost.catalog import pull

patterns = {**pull("catalog:piighost/generic"), **pull("catalog:piighost/fr")}
detector = RegexDetector(patterns)
pipeline = AnonymizationPipeline(detector)


async def main() -> None:
    result = await pipeline.anonymize(
        "IBAN FR7630006000011234567890189, email marie@exemple.fr, tel 06 12 34 56 78."
    )
    print(result.text)


asyncio.run(main())
# --8<-- [end:example]
