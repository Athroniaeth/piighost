# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost[config,fuzzy,redis,sqlalchemy,crypto,argon2]"]
#
# [tool.uv.sources]
# piighost = { path = "../..", editable = true }
# ///
"""Load every example piighost configuration and exercise each one.

The local pipeline configs (detector_only.toml, minimal.toml, minimal.json,
pipeline.toml) are anonymized end to end, with no model and no network. The two
thread pipelines are built offline, with dummy secrets and an engine that does
not connect until its first query, so they are only built (not run) here.

Run with:
uv run examples/config/run.py
"""

import asyncio
import base64
import os
from pathlib import Path

from piighost.config import load_pipeline, load_thread_pipeline

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


def _build_thread_sqlalchemy() -> None:
    """Build the SQLAlchemy thread pipeline offline, printing its memory backend.

    The database URL and the secrets are set to dummy values here; a real
    deployment reads them from the environment. create_async_engine does not
    connect, so the build stays offline; anonymizing would open the database and
    needs the table created first, so it is not called.
    """
    os.environ.setdefault("PIIGHOST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    os.environ.setdefault("PIIGHOST_HASH_PEPPER", "example-pepper")
    os.environ.setdefault("PIIGHOST_CIPHER_KEY", base64.b64encode(b"0" * 32).decode())
    pipeline = load_thread_pipeline(_HERE / "thread_sqlalchemy.toml")
    print(f"[thread_sqlalchemy.toml] built with {type(pipeline.memory).__name__}")


async def main() -> None:
    """Load every example config and show what each produces."""
    await _run_local("detector_only.toml")
    await _run_local("minimal.toml")
    await _run_local("minimal.json")
    await _run_local("pipeline.toml")
    _build_thread_redis()
    _build_thread_sqlalchemy()


if __name__ == "__main__":
    asyncio.run(main())
