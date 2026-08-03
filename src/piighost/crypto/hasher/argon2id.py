"""Argon2id hasher, the memory-hard keyed alternative (optional dependency).

This module needs the argon2-cffi package. It is guarded so that importing it
without the dependency raises an ImportError pointing at the extra to install,
rather than a bare ModuleNotFoundError. The core hasher package never imports it
eagerly, so piighost stays usable with the stdlib Sha256Hasher alone.
"""

import hashlib
import importlib.util

from piighost.crypto.hasher.base import BaseHasher

if importlib.util.find_spec("argon2") is None:
    raise ImportError(
        "Argon2Hasher requires the argon2-cffi package. "
        "Install it with: pip install piighost[argon2]"
    )

import argon2.low_level  # noqa: E402  (guarded optional import)

# Salt length in bytes for the pepper-derived salt; 16 is the argon2 default.
_SALT_LENGTH = 16
# Argon2id cost defaults, the OWASP low-memory profile (19 MiB, one pass).
_DEFAULT_TIME_COST = 2
_DEFAULT_MEMORY_COST = 19456
_DEFAULT_PARALLELISM = 1
_DEFAULT_HASH_LENGTH = 32


class Argon2Hasher(BaseHasher):
    """Key a value with the pepper through Argon2id, memory-hard.

    Argon2id is intentionally slow and memory-hard, so it resists brute-force
    even if the pepper itself leaks, at a cost that rules it out for a hot path.
    It is the interchangeable high-security alternative to the fast Sha256Hasher.

    Determinism comes from a fixed salt: Argon2 randomizes its salt by design, so
    here the salt is derived from the pepper, making the same value hash the same
    way while an attacker without the pepper cannot reproduce it.

    The cost parameters are constructor knobs so a deployment can tune the
    time and memory hardness; they default to the OWASP low-memory profile.
    """

    def __init__(
        self,
        pepper: str,
        *,
        time_cost: int = _DEFAULT_TIME_COST,
        memory_cost: int = _DEFAULT_MEMORY_COST,
        parallelism: int = _DEFAULT_PARALLELISM,
        hash_length: int = _DEFAULT_HASH_LENGTH,
    ) -> None:
        """Store the pepper and the Argon2id cost parameters."""
        super().__init__(pepper)
        self._time_cost = time_cost
        self._memory_cost = memory_cost
        self._parallelism = parallelism
        self._hash_length = hash_length

    def _digest(self, value: str) -> bytes:
        """Return Argon2id of the value, salted by a digest of the pepper."""
        salt = hashlib.sha256(self._pepper).digest()[:_SALT_LENGTH]
        return argon2.low_level.hash_secret_raw(
            secret=value.encode(),
            salt=salt,
            time_cost=self._time_cost,
            memory_cost=self._memory_cost,
            parallelism=self._parallelism,
            hash_len=self._hash_length,
            type=argon2.low_level.Type.ID,
        )
