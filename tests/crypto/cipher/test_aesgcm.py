"""Tests for the AES-GCM cipher."""

import pytest

_KEY = b"0123456789abcdef0123456789abcdef"
"""A 32-byte key, the AES-256 size."""


class TestUsableWhenInstalled:
    def test_conforms_to_the_port(self) -> None:
        """With cryptography installed, AesGcmCipher is an AnyCipher."""
        from piighost.crypto.cipher import AesGcmCipher, AnyCipher

        assert isinstance(AesGcmCipher(_KEY), AnyCipher)

    def test_round_trip_restores_plaintext(self) -> None:
        """Decrypting what was encrypted returns the original bytes."""
        from piighost.crypto.cipher import AesGcmCipher

        cipher = AesGcmCipher(_KEY)
        assert cipher.decrypt(cipher.encrypt(b"Emma")) == b"Emma"

    def test_ciphertext_hides_the_plaintext(self) -> None:
        """The ciphertext is not the plaintext in the clear."""
        from piighost.crypto.cipher import AesGcmCipher

        assert AesGcmCipher(_KEY).encrypt(b"Emma") != b"Emma"

    def test_encryption_is_randomized(self) -> None:
        """A fresh nonce per call makes the same plaintext encrypt differently."""
        from piighost.crypto.cipher import AesGcmCipher

        cipher = AesGcmCipher(_KEY)
        assert cipher.encrypt(b"Emma") != cipher.encrypt(b"Emma")

    def test_tampered_ciphertext_is_rejected(self) -> None:
        """Flipping a byte fails the authentication tag on decrypt."""
        from cryptography.exceptions import InvalidTag

        from piighost.crypto.cipher import AesGcmCipher

        cipher = AesGcmCipher(_KEY)
        blob = bytearray(cipher.encrypt(b"Emma"))
        blob[-1] ^= 0x01
        with pytest.raises(InvalidTag):
            cipher.decrypt(bytes(blob))

    def test_wrong_key_length_is_rejected(self) -> None:
        """A key that is not 16, 24, or 32 bytes fails closed."""
        from piighost.crypto.cipher import AesGcmCipher
        from piighost.exceptions import InvalidKeyLengthError

        with pytest.raises(InvalidKeyLengthError):
            AesGcmCipher(b"too-short")
