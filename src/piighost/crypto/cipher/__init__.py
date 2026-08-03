"""Ciphers: reversibly encrypt the values a repository persists.

base.py holds the AnyCipher port; concrete ciphers live in sibling modules.
AesGcmCipher needs the cryptography optional dependency, so it is imported
lazily: reaching for it without the extra raises a helpful ImportError, while
importing this package never pulls cryptography in.
"""

from typing import Any

from piighost.crypto.cipher.base import AnyCipher

__all__ = ["AesGcmCipher", "AnyCipher"]


def __getattr__(name: str) -> Any:
    """Import AesGcmCipher on demand so its optional dependency stays optional."""
    if name == "AesGcmCipher":
        from piighost.crypto.cipher.aesgcm import AesGcmCipher

        return AesGcmCipher

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
