"""Hashers: turn a value into a deterministic, pepper-keyed digest.

base.py holds the abstractions, the AnyHasher port and the BaseHasher template;
concrete hashers live in sibling modules. Sha256Hasher is stdlib and always
available. Argon2Hasher needs the argon2-cffi optional dependency, so it is
imported lazily: reaching for it without the extra raises a helpful ImportError,
while importing this package never pulls argon2-cffi in.
"""

from typing import Any

from piighost.crypto.hasher.base import AnyHasher, BaseHasher
from piighost.crypto.hasher.sha256 import Sha256Hasher

__all__ = ["AnyHasher", "Argon2Hasher", "BaseHasher", "Sha256Hasher"]


def __getattr__(name: str) -> Any:
    """Import Argon2Hasher on demand so its optional dependency stays optional."""
    if name == "Argon2Hasher":
        from piighost.crypto.hasher.argon2id import Argon2Hasher

        return Argon2Hasher

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
