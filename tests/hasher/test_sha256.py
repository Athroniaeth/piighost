"""Tests for the HMAC-SHA256 hasher."""

import pytest

from piighost.exceptions import EmptyPepperError
from piighost.hasher import AnyHasher, Sha256Hasher

_PEPPER = "pepper-secret"


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """Sha256Hasher is an AnyHasher."""
        assert isinstance(Sha256Hasher(_PEPPER), AnyHasher)


class TestHash:
    def test_is_deterministic(self) -> None:
        """The same value and pepper always hash to the same digest."""
        hasher = Sha256Hasher(_PEPPER)
        assert hasher.hash("Emma") == hasher.hash("Emma")

    def test_distinct_values_differ(self) -> None:
        """Different values hash to different digests."""
        hasher = Sha256Hasher(_PEPPER)
        assert hasher.hash("Emma") != hasher.hash("Liam")

    def test_pepper_keys_the_digest(self) -> None:
        """The same value under different peppers hashes differently."""
        assert Sha256Hasher("one").hash("Emma") != Sha256Hasher("two").hash("Emma")

    def test_digest_is_hex_sha256(self) -> None:
        """The digest is a 64-char hex string, SHA-256's 32 bytes."""
        digest = Sha256Hasher(_PEPPER).hash("Emma")
        assert len(digest) == 64
        assert bytes.fromhex(digest)

    def test_matches_hmac_sha256_not_a_plain_concatenation(self) -> None:
        """The digest is HMAC-SHA256(pepper, value), a golden value that a
        length-extension-prone sha256(pepper + value) would not reproduce."""
        expected = "a767b681d7020278e0e8e5cc3d394b8cc443d444e6e1930aec25fa364ae21f19"
        assert Sha256Hasher(_PEPPER).hash("Emma") == expected


class TestPepperGuard:
    def test_empty_pepper_is_rejected(self) -> None:
        """An empty pepper fails closed rather than hashing without a key."""
        with pytest.raises(EmptyPepperError):
            Sha256Hasher("")
