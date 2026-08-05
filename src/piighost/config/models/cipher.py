"""Cipher configuration model.

The key is a secret read from the PIIGHOST_CIPHER_KEY environment variable,
base64-encoded, never from the TOML. build() requires it and raises a ConfigError
when it is unset or not valid base64.
"""

import base64
import binascii
import os
from typing import Literal

from piighost.config.models.common import _ComponentConfig
from piighost.crypto.cipher.base import AnyCipher
from piighost.exceptions import ConfigError

_CIPHER_KEY_ENV = "PIIGHOST_CIPHER_KEY"
"""The environment variable holding the base64 AES key the cipher uses."""


class AesGcmCipherConfig(_ComponentConfig):
    """Config for the AES-GCM cipher, authenticated encryption of stored values."""

    type: Literal["aesgcm"]

    def build(self) -> AnyCipher:
        """Build an AesGcmCipher from the base64 key in the environment.

        Raises:
            ConfigError: If PIIGHOST_CIPHER_KEY is unset or not valid base64.
        """
        from piighost.crypto.cipher.aesgcm import AesGcmCipher

        encoded = os.environ.get(_CIPHER_KEY_ENV)
        if not encoded:
            raise ConfigError(
                f"the cipher requires the {_CIPHER_KEY_ENV} environment variable "
                "to be set"
            )
        try:
            key = base64.b64decode(encoded, validate=True)
        except binascii.Error as exc:
            raise ConfigError(f"{_CIPHER_KEY_ENV} must be valid base64: {exc}") from exc
        return AesGcmCipher(key)


CipherConfig = AesGcmCipherConfig
"""The cipher configuration.

A plain alias while one cipher exists; it becomes a discriminated union when a
second cipher lands.
"""
