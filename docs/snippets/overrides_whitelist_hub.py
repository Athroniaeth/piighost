import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import RegexDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.override import DetectionOverride
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline

detector = RegexDetector.from_hub("hub:piighost/generic")
whitelist = RegexDetector({"CODENAME": r"ACME-[A-Z]+"})
override = DetectionOverride(whitelist=whitelist)
linker = ExactEntityLinker()
factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
pipeline = AnonymizationPipeline(
    detector,
    linker,
    anonymizer,
    override=override,
)


async def main():
    result = await pipeline.anonymize("Ship ACME-FALCON to alice@example.com.")
    print(result.text)
    # Ship <<CODENAME:1>> to <<EMAIL:1>>.


asyncio.run(main())
