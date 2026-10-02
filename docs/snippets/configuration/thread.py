import asyncio

from piighost.config import load_thread_pipeline


async def main() -> None:
    pipeline = load_thread_pipeline("pipeline.toml")
    first = await pipeline.anonymize("Patrick writes to alice@corp.com.", "thread-42")
    print(first.text)
    second = await pipeline.anonymize("Patrik answers from 10.0.0.7.", "thread-42")
    print(second.text)


asyncio.run(main())
