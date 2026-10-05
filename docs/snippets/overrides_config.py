import asyncio

from piighost.config import load_pipeline

pipeline = load_pipeline("pipeline.toml")


async def main() -> None:
    result = await pipeline.anonymize(
        "Mail public@corp.com or alice@example.com about ACME-FALCON."
    )
    print(result.text)


asyncio.run(main())
