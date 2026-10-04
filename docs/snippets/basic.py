# --8<-- [start:hub]
import asyncio

from piighost.components.detector import RegexDetector
from piighost.pipeline import AnonymizationPipeline

detector = RegexDetector.from_hub("hub:piighost/generic")
pipeline = AnonymizationPipeline(detector)


async def main() -> None:
    result = await pipeline.anonymize("Contact alice@example.com from 192.168.1.42.")
    print(result.text)

    restored = pipeline.deanonymize(result.text, result.tokens)
    print(restored)


asyncio.run(main())
# --8<-- [end:hub]


# --8<-- [start:reply]
async def main() -> None:
    result = await pipeline.anonymize("Contact alice@example.com from 192.168.1.42.")

    llm_reply = "I sent the message to <<EMAIL:1>>."
    print(pipeline.deanonymize(llm_reply, result.tokens))


asyncio.run(main())
# --8<-- [end:reply]
