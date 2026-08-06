# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost[config,fuzzy,client,redis,crypto,argon2]"]
#
# [tool.uv.sources]
# piighost = { path = "../..", editable = true }
# ///
"""Load every example piighost configuration and exercise each one.

The local pipeline configs (minimal.toml, minimal.json, pipeline.toml) are
anonymized end to end, with no model and no network. The Redis thread pipeline
is built offline, with dummy secrets and a client that does not connect until
its first command, so it is only built (not run) here. The remote client is
built offline too, since calling it would need a running piighost-api.

Run with:
uv run examples/config/run.py
"""

import asyncio
import base64
import os
from pathlib import Path

from piighost.config import (
    load_client,
    load_pipeline,
    load_thread_pipeline,
)

_HERE = Path(__file__).parent
_SAMPLE = "Email alice@corp.com and bob@corp.com about ACME-SECRET, ref EMP-1234."


async def _run_local(name: str) -> None:
    """Load a local pipeline config and anonymize the sample message."""
    pipeline = load_pipeline(_HERE / name)
    result = await pipeline.anonymize(_SAMPLE)
    print(f"[{name}] {result.text}")


def _build_thread_redis() -> None:
    """Build the Redis thread pipeline offline, printing its memory backend.

    The secrets are set to dummy values here; a real deployment reads them from
    the environment. Redis.from_url does not connect, so the build stays offline;
    anonymizing would reach Redis, so it is not called.
    """
    os.environ.setdefault("PIIGHOST_HASH_PEPPER", "example-pepper")
    os.environ.setdefault("PIIGHOST_CIPHER_KEY", base64.b64encode(b"0" * 32).decode())
    pipeline = load_thread_pipeline(_HERE / "thread_redis.toml")
    print(f"[thread_redis.toml] built with {type(pipeline.memory).__name__}")


def _build_client() -> None:
    """Build the remote client offline, printing its token recognizer."""
    client = load_client(_HERE / "remote_client.toml")
    print(f"[remote_client.toml] client with {type(client.recognizer).__name__}")


async def main() -> None:
    """Load every example config and show what each produces."""
    await _run_local("minimal.toml")
    await _run_local("minimal.json")
    await _run_local("pipeline.toml")
    _build_thread_redis()
    _build_client()


if __name__ == "__main__":
    asyncio.run(main())
