# Not shown: the server the page assumes at 127.0.0.1:8000, which the test starts
# on a free port.
from _offline import serve_locally

serve_locally()

# isort: split
# --8<-- [start:example]
import asyncio
import os

from piighost.integrations.client import PIIGhostClient


async def main() -> None:
    headers = {"Authorization": f"Bearer {os.environ['API_KEY_DEV']}"}
    async with PIIGhostClient("http://127.0.0.1:8000", headers=headers) as client:
        result = await client.anonymize("Hi, I am Jane Doe.", thread_id="demo")
        print(result.text)


asyncio.run(main())
# --8<-- [end:example]
