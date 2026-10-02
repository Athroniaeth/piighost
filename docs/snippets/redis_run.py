# Not shown: the secrets the page exports, and a Redis held in memory in place of
# redis.internal.
from _offline import offline_redis

offline_redis()

# isort: split
# --8<-- [start:example]
from piighost.config import load_thread_pipeline

pipeline = load_thread_pipeline("pipeline.toml")

result = await pipeline.anonymize(
    "Write to alice@corp.com from 10.0.0.7.", thread_id="user-42"
)
print(result.text)  # Write to <<EMAIL:1>> from <<IPV4:1>>.
# --8<-- [end:example]
