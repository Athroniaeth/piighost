# --8<-- [start:setup]
import asyncio

from piighost.components.detector import ExactMatchDetector
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.pipeline import ThreadAnonymizationPipeline

detector = ExactMatchDetector({"Patrick": "PERSON", "Paris": "LOCATION"})
memory = InMemoryConversationMemory()
pipeline = ThreadAnonymizationPipeline(detector, memory=memory)
# --8<-- [end:setup]


# --8<-- [start:turns]
async def main() -> None:
    first = await pipeline.anonymize("Patrick habite à Paris.", "thread-42")
    print(first.text)

    second = await pipeline.anonymize("Est-ce que Patrick aime Paris ?", "thread-42")
    print(second.text)
    # --8<-- [end:turns]

    # --8<-- [start:restore]
    restored = await pipeline.deanonymize("Bonjour <<PERSON:1>> !", "thread-42")
    print(restored)
    # Bonjour Patrick !
    # --8<-- [end:restore]

    # --8<-- [start:forget]
    forgotten = await pipeline.forget_thread("thread-42")
    print(forgotten)
    # Forgotten(messages=2, detections=4)
    # --8<-- [end:forget]


# --8<-- [start:run]
asyncio.run(main())
# --8<-- [end:run]
