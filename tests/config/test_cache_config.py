"""TOML [cache] section: backend selection with env-var URL indirection."""

import pytest
from aiocache import SimpleMemoryCache

from piighost.config import load_config
from piighost.config.builders import build_cache
from piighost.config.errors import ConfigError
from piighost.config.models.cache import (
    MemoryCacheConfig,
    RedisCacheConfig,
    SqlAlchemyCacheConfig,
)

MINIMAL_DETECTOR = r"""
[[detectors]]
type = "regex"
[detectors.patterns]
EMAIL = '\S+@\S+'
"""


def _write_toml(tmp_path, body: str):
    path = tmp_path / "pipeline.toml"
    path.write_text(body)
    return path


def test_cache_section_defaults_to_memory(tmp_path):
    cfg = load_config(_write_toml(tmp_path, MINIMAL_DETECTOR))
    assert isinstance(cfg.cache, MemoryCacheConfig)
    assert isinstance(build_cache(cfg.cache), SimpleMemoryCache)


def test_redis_cache_reads_url_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_REDIS", "redis://localhost:1/0")
    cfg = load_config(
        _write_toml(
            tmp_path,
            '[cache]\ntype = "redis"\nurl_env = "MY_REDIS"\n' + MINIMAL_DETECTOR,
        )
    )
    assert isinstance(cfg.cache, RedisCacheConfig)
    cache = build_cache(cfg.cache)
    # No connection happens at construction; just check the backend type.
    assert type(cache).__name__ == "RedisCache"


def test_redis_cache_missing_env_var_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("MY_REDIS", raising=False)
    cfg = load_config(
        _write_toml(
            tmp_path,
            '[cache]\ntype = "redis"\nurl_env = "MY_REDIS"\n' + MINIMAL_DETECTOR,
        )
    )
    with pytest.raises(ConfigError, match="MY_REDIS"):
        build_cache(cfg.cache)


def test_sqlalchemy_cache_reads_url_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_DB", "sqlite+aiosqlite:///:memory:")
    cfg = load_config(
        _write_toml(
            tmp_path,
            '[cache]\ntype = "sqlalchemy"\nurl_env = "MY_DB"\ntable_name = "pii"\n'
            + MINIMAL_DETECTOR,
        )
    )
    assert isinstance(cfg.cache, SqlAlchemyCacheConfig)
    cache = build_cache(cfg.cache)
    assert type(cache).__name__ == "SQLAlchemyCache"


def test_load_pipeline_wires_the_cache(tmp_path):
    from piighost.config import load_pipeline

    pipeline, _ = load_pipeline(_write_toml(tmp_path, MINIMAL_DETECTOR))
    assert isinstance(pipeline._cache, SimpleMemoryCache)
