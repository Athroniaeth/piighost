# Not shown: the secrets the page exports, and a Redis held in memory in place of
# redis.internal.
from _offline import offline_redis

offline_redis()

# isort: split
# --8<-- [start:example]
import asyncio

from piighost.config import load_thread_pipeline

pipeline = load_thread_pipeline("pipeline.toml")


async def main() -> None:
    result = await pipeline.anonymize(
        "Write to alice@corp.com from 10.0.0.7.", thread_id="user-42"
    )
    print(result.text)


asyncio.run(main())
# --8<-- [end:example]
