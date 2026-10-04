# Not shown: the server the page assumes at 127.0.0.1:8000, which the test starts
# on a free port.
from _offline import serve_locally

serve_locally()

# isort: split
# --8<-- [start:example]
import asyncio

from piighost.integrations.client import PIIGhostClient


async def main() -> None:
    async with PIIGhostClient("http://127.0.0.1:8000") as client:
        result = await client.anonymize(
            "Patrick lives in Paris.", thread_id="thread-42"
        )
        print(result.text)

        restored = await client.deanonymize(result.text, thread_id="thread-42")
        print(restored)


asyncio.run(main())
# --8<-- [end:example]
