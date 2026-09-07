"""Argon2id hasher, the memory-hard keyed alternative (optional dependency).

This module needs the argon2-cffi package. It is guarded so that importing it
without the dependency raises an ImportError pointing at the extra to install,
rather than a bare ModuleNotFoundError. The core hasher package never imports it
eagerly, so piighost stays usable with the stdlib Sha256Hasher alone.
"""

import hashlib
import hmac
import importlib.util

from piighost.crypto.hasher.base import BaseHasher

if importlib.util.find_spec("argon2") is None:
    raise ImportError(
        "Argon2Hasher requires the argon2-cffi package. "
        "Install it with: pip install piighost[argon2]"
    )

import argon2.low_level

_SALT_LENGTH = 16
"""Salt length in bytes for the pepper-derived salt, the argon2 default."""

_DEFAULT_TIME_COST = 2
"""Argon2id time cost in passes, the OWASP low-memory profile of one pass."""

_DEFAULT_MEMORY_COST = 19456
"""Argon2id memory cost in KiB, the OWASP low-memory profile of 19 MiB."""

_DEFAULT_PARALLELISM = 1
"""Argon2id parallelism in lanes, the OWASP low-memory profile of one lane."""

_DEFAULT_HASH_LENGTH = 32
"""Argon2id raw output length in bytes."""


class Argon2Hasher(BaseHasher):
    """Key a value with the pepper through Argon2id, memory-hard.

    Argon2id is intentionally slow and memory-hard, so it resists brute-force
    even if the pepper itself leaks, at a cost that rules it out for a hot path.
    It is the interchangeable high-security alternative to the fast Sha256Hasher.

    The pepper keys the digest twice over. The value is first HMAC-SHA256'd under
    the pepper, and that keyed digest is what Argon2id hashes, so the pepper enters
    through a standard keyed PRF rather than through the salt alone. argon2-cffi
    does not expose Argon2's own key parameter, hence the HMAC.

    Determinism comes from a fixed salt: Argon2 randomizes its salt by design, so
    here the salt is derived from the pepper, making the same value hash the same
    way. The salt is not the security boundary though, since Argon2 treats a salt
    as public, which is why the HMAC above carries the keying.

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
        """Return Argon2id of the pepper-keyed value, salted by a digest of the pepper.

        Handing an attacker the salt is not enough to recompute a digest, because
        the message Argon2id sees is already keyed by the pepper.
        """
        salt = hashlib.sha256(self._pepper).digest()[:_SALT_LENGTH]
        keyed_value = hmac.new(self._pepper, value.encode(), hashlib.sha256).digest()
        return argon2.low_level.hash_secret_raw(
            secret=keyed_value,
            salt=salt,
            time_cost=self._time_cost,
            memory_cost=self._memory_cost,
            parallelism=self._parallelism,
            hash_len=self._hash_length,
            type=argon2.low_level.Type.ID,
        )
