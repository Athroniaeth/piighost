"""Cipher abstractions: the port for reversible encryption at rest.

A cipher protects the values a repository persists: the store keeps ciphertext,
so a leak of the database or cache yields nothing usable without the key held
outside it. The values must round-trip, so this is encryption, not hashing.

There is no Base template. A symmetric backend and an asymmetric one differ by
their whole mechanism, nonce handling, key model, not by a single hook over one
input, so there is no shared skeleton to template. This is the pairwise
exception to the always-template rule.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class AnyCipher(Protocol):
    """A component that reversibly encrypts and decrypts bytes."""

    def encrypt(self, plaintext: bytes) -> bytes:
        """Return the ciphertext for the given plaintext.

        Args:
            plaintext: The bytes to encrypt.

        Returns:
            The ciphertext, self-contained so decrypt can reverse it.
        """
        ...

    def decrypt(self, ciphertext: bytes) -> bytes:
        """Return the plaintext for the given ciphertext.

        Args:
            ciphertext: The bytes previously returned by encrypt.

        Returns:
            The original plaintext.
        """
        ...
