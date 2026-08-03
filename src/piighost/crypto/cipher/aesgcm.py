"""AES-GCM cipher, symmetric authenticated encryption (optional dependency).

This module needs the cryptography package. It is guarded so that importing it
without the dependency raises an ImportError pointing at the extra to install.
The core cipher package never imports it eagerly.
"""

import importlib.util
import os

from piighost.exceptions import InvalidKeyLengthError

if importlib.util.find_spec("cryptography") is None:
    raise ImportError(
        "AesGcmCipher requires the cryptography package. "
        "Install it with: pip install piighost[crypto]"
    )

from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: E402

_NONCE_LENGTH = 12
"""AES-GCM nonce length in bytes, the 96-bit size the mode is defined for, prepended to each ciphertext."""

_VALID_KEY_LENGTHS = (16, 24, 32)
"""Accepted AES key sizes in bytes, for AES-128, AES-192, and AES-256."""


class AesGcmCipher:
    """Encrypt bytes with AES-GCM under a key held outside the store.

    AES-GCM is authenticated encryption: it both hides the plaintext and detects
    any tampering, failing to decrypt an altered ciphertext. A fresh random
    nonce is drawn per message and prepended to the ciphertext, so encrypting the
    same plaintext twice yields different output. Security rests on the key
    living outside the store (an environment variable or KMS), so a leak of the
    persisted ciphertext alone reveals nothing.

    Both encrypting and decrypting need the same key, so this suits a process
    that anonymizes and deanonymizes together; an asymmetric cipher is the
    alternative when those roles live in separate trust zones.

    Raises:
        InvalidKeyLengthError: If the key is not 16, 24, or 32 bytes.
    """

    def __init__(self, key: bytes) -> None:
        """Store an AES-GCM cipher for the key, rejecting a wrong-sized one."""
        if len(key) not in _VALID_KEY_LENGTHS:
            raise InvalidKeyLengthError(
                f"An AES key must be 16, 24, or 32 bytes, got {len(key)}"
            )

        self._aead = AESGCM(key)

    def encrypt(self, plaintext: bytes) -> bytes:
        """Return a fresh nonce followed by the authenticated ciphertext."""
        nonce = os.urandom(_NONCE_LENGTH)
        sealed = self._aead.encrypt(nonce, plaintext, None)
        return nonce + sealed

    def decrypt(self, ciphertext: bytes) -> bytes:
        """Split the leading nonce off and decrypt the authenticated ciphertext."""
        nonce = ciphertext[:_NONCE_LENGTH]
        sealed = ciphertext[_NONCE_LENGTH:]
        return self._aead.decrypt(nonce, sealed, None)
