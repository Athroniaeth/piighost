# Not shown: the server the page assumes at 127.0.0.1:8000, which the test starts
# on a free port, and the message of the previous step, in the thread forgotten here.
import asyncio

from _offline import serve_locally

from piighost.integrations.client import PIIGhostClient as Client

serve_locally()


async def previous_step() -> None:
    async with Client("http://127.0.0.1:8000") as client:
        await client.anonymize("Patrick habite à Paris.", thread_id="thread-42")


asyncio.run(previous_step())

# isort: split
# --8<-- [start:example]
import asyncio

from piighost.integrations.client import PIIGhostClient


async def main() -> None:
    async with PIIGhostClient("http://127.0.0.1:8000") as client:
        forgotten = await client.forget_thread(thread_id="thread-42")
        print(forgotten)


asyncio.run(main())
# --8<-- [end:example]
