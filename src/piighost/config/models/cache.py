"""Cache backend configuration models.

Connection URLs are NEVER stored in the TOML: each backend names an
environment variable (``url_env``) holding the URL, so one config file
works across environments and secrets stay out of version control
(same philosophy as the hash pepper).
"""

from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.config.models.common import _ComponentConfig


class MemoryCacheConfig(_ComponentConfig):
    """Process-local in-memory cache (the default).

    Suitable for single-process deployments only: mappings are lost on
    restart and not shared across workers.
    """

    type: Literal["memory"] = "memory"


class RedisCacheConfig(_ComponentConfig):
    """Redis backend via aiocache. Requires the ``redis`` extra."""

    type: Literal["redis"]
    url_env: str = "REDIS_URL"
    """Environment variable holding the redis:// connection URL."""


class SqlAlchemyCacheConfig(_ComponentConfig):
    """SQL backend via piighost.cache.SQLAlchemyCache. Requires the ``sqlalchemy`` extra."""

    type: Literal["sqlalchemy"]
    url_env: str = "DATABASE_URL"
    """Environment variable holding the SQLAlchemy async URL."""
    table_name: str = Field(default="piighost_cache", min_length=1)


CacheConfig = Annotated[
    MemoryCacheConfig | RedisCacheConfig | SqlAlchemyCacheConfig,
    Discriminator("type"),
]
