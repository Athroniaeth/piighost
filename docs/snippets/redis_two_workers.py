# Not shown: the secrets the page exports, and a Redis held in memory in place of
# redis.internal.
from _offline import offline_redis

offline_redis()

# isort: split
# --8<-- [start:example]
import asyncio

from piighost.config import load_thread_pipeline

worker_a = load_thread_pipeline("pipeline.toml")
worker_b = load_thread_pipeline("pipeline.toml")


async def main() -> None:
    first = await worker_a.anonymize("Write to alice@corp.com.", thread_id="user-42")
    second = await worker_b.anonymize(
        "Copy bob@corp.com, then alice@corp.com.", thread_id="user-42"
    )
    print(first.text)
    print(second.text)


asyncio.run(main())
# --8<-- [end:example]
