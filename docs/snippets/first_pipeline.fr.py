# --8<-- [start:detector]
from piighost.components.detector import RegexDetector

patterns = {
    "PERSON": r"\b(?:Patrick|Marie)\b",
    "LOCATION": r"\bParis\b",
}
detector = RegexDetector(patterns)
# --8<-- [end:detector]

# --8<-- [start:linker]
from piighost.components.linker import ExactEntityLinker

linker = ExactEntityLinker()
# --8<-- [end:linker]

# --8<-- [start:anonymizer]
from piighost.components.anonymizer import Anonymizer
from piighost.components.placeholder import LabelCounterPlaceholderFactory

factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
# --8<-- [end:anonymizer]

# --8<-- [start:run]
import asyncio

from piighost.pipeline import AnonymizationPipeline

pipeline = AnonymizationPipeline(detector, linker, anonymizer)


async def main() -> None:
    text = "Patrick habite à Paris. Patrick aime Paris. Marie aussi."
    result = await pipeline.anonymize(text)
    print(result.text)


asyncio.run(main())
# --8<-- [end:run]
