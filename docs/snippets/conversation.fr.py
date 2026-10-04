# --8<-- [start:setup]
import asyncio

from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import ThreadAnonymizationPipeline

detector = ExactMatchDetector({"Patrick": "PERSON", "Paris": "LOCATION"})
pipeline = ThreadAnonymizationPipeline(detector)
# --8<-- [end:setup]


# --8<-- [start:turns]
async def main() -> None:
    first = await pipeline.anonymize("Patrick habite à Paris.", thread_id="thread-42")
    print(first.text)

    second = await pipeline.anonymize(
        "Est-ce que Patrick aime Paris ?", thread_id="thread-42"
    )
    print(second.text)


asyncio.run(main())
# --8<-- [end:turns]


# --8<-- [start:restore]
async def main() -> None:
    restored = await pipeline.deanonymize(
        "Bonjour <<PERSON:1>> !", thread_id="thread-42"
    )
    print(restored)


asyncio.run(main())
# --8<-- [end:restore]


# --8<-- [start:forget]
async def main() -> None:
    forgotten = await pipeline.forget_thread(thread_id="thread-42")
    print(forgotten)


asyncio.run(main())
# --8<-- [end:forget]
