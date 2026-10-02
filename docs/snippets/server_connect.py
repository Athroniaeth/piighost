import asyncio

from piighost.integrations.client import PIIGhostClient


async def main() -> None:
    async with PIIGhostClient(
        "http://localhost:8000",
        timeout=10.0,
        headers={"Authorization": "Bearer ..."},
        retries=2,
    ) as client:
        ...


asyncio.run(main())
