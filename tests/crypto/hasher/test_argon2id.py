"""Tests for the Argon2id hasher."""

import hashlib

import pytest


class TestUsableWhenInstalled:
    def test_conforms_to_the_port(self) -> None:
        """With argon2-cffi installed, Argon2Hasher is an AnyHasher."""
        from piighost.crypto.hasher import AnyHasher, Argon2Hasher

        assert isinstance(Argon2Hasher("pepper-secret"), AnyHasher)

    def test_installed_argon2_hashes_deterministically(self) -> None:
        """A digest is a 64-char hex string and stable across calls."""
        from piighost.crypto.hasher import Argon2Hasher

        hasher = Argon2Hasher("pepper-secret")
        digest = hasher.hash("Emma")
        assert len(digest) == 64
        assert bytes.fromhex(digest)
        assert hasher.hash("Emma") == digest

    def test_distinct_values_differ(self) -> None:
        """Different values hash to different digests."""
        from piighost.crypto.hasher import Argon2Hasher

        hasher = Argon2Hasher("pepper-secret")
        assert hasher.hash("Emma") != hasher.hash("Liam")

    def test_pepper_keys_the_digest(self) -> None:
        """The same value under different peppers hashes differently."""
        from piighost.crypto.hasher import Argon2Hasher

        assert Argon2Hasher("one").hash("Emma") != Argon2Hasher("two").hash("Emma")

    def test_empty_pepper_is_rejected(self) -> None:
        """Argon2Hasher inherits the fail-closed empty-pepper guard."""
        from piighost.crypto.hasher import Argon2Hasher
        from piighost.exceptions import EmptyPepperError

        with pytest.raises(EmptyPepperError):
            Argon2Hasher("")

    def test_hash_length_is_configurable(self) -> None:
        """A custom hash length sizes the digest, hex being twice the bytes."""
        from piighost.crypto.hasher import Argon2Hasher

        assert len(Argon2Hasher("pepper-secret", hash_length=16).hash("Emma")) == 32

    def test_the_pepper_keys_the_value_not_only_the_salt(self) -> None:
        """The digest differs from a bare Argon2id over the same value and salt.

        The salt alone carried the pepper before this change, and Argon2 treats a
        salt as public, so the value is now HMAC-ed under the pepper first.
        """
        import argon2.low_level

        from piighost.crypto.hasher import Argon2Hasher, argon2id

        pepper = "pepper-secret"
        salt = hashlib.sha256(pepper.encode()).digest()[: argon2id._SALT_LENGTH]
        unkeyed = argon2.low_level.hash_secret_raw(
            secret=b"Emma",
            salt=salt,
            time_cost=argon2id._DEFAULT_TIME_COST,
            memory_cost=argon2id._DEFAULT_MEMORY_COST,
            parallelism=argon2id._DEFAULT_PARALLELISM,
            hash_len=argon2id._DEFAULT_HASH_LENGTH,
            type=argon2.low_level.Type.ID,
        )
        assert Argon2Hasher(pepper).hash("Emma") != unkeyed.hex()

    def test_cost_parameters_change_the_digest(self) -> None:
        """A different Argon2 cost yields a different digest for the same input."""
        from piighost.crypto.hasher import Argon2Hasher

        cheap = Argon2Hasher("pepper-secret", time_cost=1).hash("Emma")
        dearer = Argon2Hasher("pepper-secret", time_cost=3).hash("Emma")
        assert cheap != dearer
