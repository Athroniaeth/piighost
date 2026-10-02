import asyncio
import sys

from piighost.config import load_pipeline


async def main() -> None:
    pipeline = load_pipeline("pipeline.toml")
    result = await pipeline.anonymize(sys.argv[1])
    print(result.text)


asyncio.run(main())
