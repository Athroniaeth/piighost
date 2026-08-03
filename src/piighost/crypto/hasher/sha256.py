"""HMAC-SHA256 hasher, the fast keyed default."""

import hashlib
import hmac

from piighost.crypto.hasher.base import BaseHasher


class Sha256Hasher(BaseHasher):
    """Key a value with the pepper through HMAC-SHA256.

    HMAC is the correct keyed construction: it resists the length-extension
    weakness of a plain sha256(pepper + value) concatenation. It is fast, so it
    fits the hot path where a key is computed on every message, at the cost of
    offering no extra resistance should the pepper itself leak. For that threat
    an Argon2 hasher is the interchangeable alternative.
    """

    def _digest(self, value: str) -> bytes:
        """Return HMAC-SHA256 of the value keyed by the pepper."""
        return hmac.new(self._pepper, value.encode(), hashlib.sha256).digest()
