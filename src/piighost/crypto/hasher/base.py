"""Hasher abstractions: the port and a shared pepper-and-hexlify template.

A hasher turns a value into a deterministic, keyed digest: the same value under
the same pepper always yields the same string, so it can serve as a stable
lookup key, while an attacker without the pepper can neither reverse nor
brute-force it. It is used to key low-entropy PII (a message, a value) in a
persistent store without leaking the plaintext.
"""

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

from piighost.exceptions import EmptyPepperError


@runtime_checkable
class AnyHasher(Protocol):
    """A component that turns a value into a deterministic, keyed digest."""

    def hash(self, value: str) -> str:
        """Return the digest of a value as a hex string.

        Args:
            value: The value to hash.

        Returns:
            The digest, a hex string, stable across calls for one pepper.
        """
        ...


class BaseHasher(ABC):
    """Hold the pepper and hexlify a subclass-defined raw digest.

    The skeleton lives here: reject an empty pepper up front, then render every
    digest as a hex string. A subclass defines _digest, the raw bytes for a
    value under the stored pepper, which is where the hashing primitive, HMAC or
    Argon2, actually differs.

    Raises:
        EmptyPepperError: If the pepper is empty.
    """

    def __init__(self, pepper: str) -> None:
        """Store the pepper as bytes, refusing an empty one to stay keyed."""
        if not pepper:
            raise EmptyPepperError("A hasher needs a non-empty pepper")

        self._pepper = pepper.encode()

    def hash(self, value: str) -> str:
        """Return the raw digest of a value rendered as a hex string."""
        return self._digest(value).hex()

    @abstractmethod
    def _digest(self, value: str) -> bytes:
        """Return the raw digest bytes of a value under the stored pepper."""
        ...
