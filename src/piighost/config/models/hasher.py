"""Hasher configuration models, discriminated on type.

The pepper is a secret read from the PIIGHOST_HASH_PEPPER environment variable,
never from the TOML, so it is not committed. build() requires it and raises a
ConfigError when it is unset.
"""

import os
from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.config.models.common import _ComponentConfig
from piighost.crypto.hasher.base import AnyHasher
from piighost.exceptions import ConfigError

_HASH_PEPPER_ENV = "PIIGHOST_HASH_PEPPER"
"""The environment variable holding the pepper that keys every hasher."""


def _read_pepper() -> str:
    """Return the hash pepper from the environment.

    Raises:
        ConfigError: If PIIGHOST_HASH_PEPPER is unset or empty.
    """
    pepper = os.environ.get(_HASH_PEPPER_ENV)
    if not pepper:
        raise ConfigError(
            f"a hasher requires the {_HASH_PEPPER_ENV} environment variable to be set"
        )
    return pepper


class Sha256HasherConfig(_ComponentConfig):
    """Config for the HMAC-SHA256 hasher, a fast keyed digest."""

    type: Literal["sha256"]

    def build(self) -> AnyHasher:
        """Build a Sha256Hasher keyed by the environment pepper."""
        from piighost.crypto.hasher.sha256 import Sha256Hasher

        return Sha256Hasher(_read_pepper())


class Argon2HasherConfig(_ComponentConfig):
    """Config for the Argon2id hasher, a slow memory-hard digest.

    Attributes:
        time_cost: The number of Argon2 iterations.
        memory_cost: The memory in kibibytes Argon2 uses.
        parallelism: The number of parallel lanes.
        hash_length: The digest length in bytes.
    """

    type: Literal["argon2"]
    time_cost: int = Field(default=2, ge=1)
    memory_cost: int = Field(default=19456, ge=1)
    parallelism: int = Field(default=1, ge=1)
    hash_length: int = Field(default=32, ge=1)

    def build(self) -> AnyHasher:
        """Build an Argon2Hasher keyed by the environment pepper."""
        from piighost.crypto.hasher.argon2id import Argon2Hasher

        return Argon2Hasher(
            _read_pepper(),
            time_cost=self.time_cost,
            memory_cost=self.memory_cost,
            parallelism=self.parallelism,
            hash_length=self.hash_length,
        )


HasherConfig = Annotated[
    Sha256HasherConfig | Argon2HasherConfig,
    Discriminator("type"),
]
