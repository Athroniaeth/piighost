"""Tests for the AES-GCM cipher and its optional-dependency guard."""

import importlib
import importlib.util
import sys

import pytest

_MODULE = "piighost.crypto.cipher.aesgcm"
_KEY = b"0123456789abcdef0123456789abcdef"  # 32 bytes, AES-256


class TestOptionalDependencyGuard:
    def test_missing_cryptography_explains_how_to_install(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Importing without cryptography points the user at piighost[crypto]."""
        real_find_spec = importlib.util.find_spec

        def find_spec(name: str, *args: object, **kwargs: object) -> object:
            if name == "cryptography":
                return None
            return real_find_spec(name, *args, **kwargs)

        monkeypatch.setattr(importlib.util, "find_spec", find_spec)
        sys.modules.pop(_MODULE, None)

        with pytest.raises(ImportError, match=r"piighost\[crypto\]"):
            importlib.import_module(_MODULE)

        sys.modules.pop(_MODULE, None)


class TestUsableWhenInstalled:
    def test_conforms_to_the_port(self) -> None:
        """With cryptography installed, AesGcmCipher is an AnyCipher."""
        pytest.importorskip("cryptography")
        from piighost.crypto.cipher import AesGcmCipher, AnyCipher

        assert isinstance(AesGcmCipher(_KEY), AnyCipher)

    def test_round_trip_restores_plaintext(self) -> None:
        """Decrypting what was encrypted returns the original bytes."""
        pytest.importorskip("cryptography")
        from piighost.crypto.cipher import AesGcmCipher

        cipher = AesGcmCipher(_KEY)
        assert cipher.decrypt(cipher.encrypt(b"Emma")) == b"Emma"

    def test_ciphertext_hides_the_plaintext(self) -> None:
        """The ciphertext is not the plaintext in the clear."""
        pytest.importorskip("cryptography")
        from piighost.crypto.cipher import AesGcmCipher

        assert AesGcmCipher(_KEY).encrypt(b"Emma") != b"Emma"

    def test_encryption_is_randomized(self) -> None:
        """A fresh nonce per call makes the same plaintext encrypt differently."""
        pytest.importorskip("cryptography")
        from piighost.crypto.cipher import AesGcmCipher

        cipher = AesGcmCipher(_KEY)
        assert cipher.encrypt(b"Emma") != cipher.encrypt(b"Emma")

    def test_tampered_ciphertext_is_rejected(self) -> None:
        """Flipping a byte fails the authentication tag on decrypt."""
        pytest.importorskip("cryptography")
        from cryptography.exceptions import InvalidTag

        from piighost.crypto.cipher import AesGcmCipher

        cipher = AesGcmCipher(_KEY)
        blob = bytearray(cipher.encrypt(b"Emma"))
        blob[-1] ^= 0x01
        with pytest.raises(InvalidTag):
            cipher.decrypt(bytes(blob))

    def test_wrong_key_length_is_rejected(self) -> None:
        """A key that is not 16, 24, or 32 bytes fails closed."""
        pytest.importorskip("cryptography")
        from piighost.crypto.cipher import AesGcmCipher
        from piighost.exceptions import InvalidKeyLengthError

        with pytest.raises(InvalidKeyLengthError):
            AesGcmCipher(b"too-short")
