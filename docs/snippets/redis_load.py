# Not shown: the secrets the page exports, and a Redis held in memory in place of
# redis.internal.
from _offline import offline_redis

offline_redis()

# isort: split
# --8<-- [start:example]
from piighost.config import load_thread_pipeline

pipeline = load_thread_pipeline("pipeline.toml")
# --8<-- [end:example]
