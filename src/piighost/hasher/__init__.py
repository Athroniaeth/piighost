"""Hashers: turn a value into a deterministic, pepper-keyed digest.

base.py holds the abstractions, the AnyHasher port and the BaseHasher template;
concrete hashers live in sibling modules.
"""

from piighost.hasher.base import AnyHasher, BaseHasher
from piighost.hasher.sha256 import Sha256Hasher

__all__ = ["AnyHasher", "BaseHasher", "Sha256Hasher"]
