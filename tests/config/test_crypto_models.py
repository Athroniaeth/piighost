"""Tests for the hasher and cipher config models."""

import base64

import pytest
from pydantic import TypeAdapter, ValidationError

from piighost.config.models.cipher import AesGcmCipherConfig
from piighost.config.models.hasher import (
    Argon2HasherConfig,
    HasherConfig,
    Sha256HasherConfig,
)
from piighost.crypto.cipher.aesgcm import AesGcmCipher
from piighost.crypto.hasher.argon2id import Argon2Hasher
from piighost.crypto.hasher.sha256 import Sha256Hasher
from piighost.exceptions import ConfigError

_KEY_B64 = base64.b64encode(b"0" * 32).decode()


class TestHasherConfig:
    def test_sha256_builds_with_env_pepper(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The sha256 config builds a Sha256Hasher keyed by the env pepper."""
        monkeypatch.setenv("PIIGHOST_HASH_PEPPER", "secret")
        assert isinstance(Sha256HasherConfig(type="sha256").build(), Sha256Hasher)

    def test_argon2_builds_and_stores_costs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The argon2 config builds an Argon2Hasher and keeps its cost fields."""
        monkeypatch.setenv("PIIGHOST_HASH_PEPPER", "secret")
        config = Argon2HasherConfig(type="argon2", time_cost=3, memory_cost=1024)
        assert config.time_cost == 3
        assert config.memory_cost == 1024
        assert isinstance(config.build(), Argon2Hasher)

    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            ({"type": "sha256"}, Sha256HasherConfig),
            ({"type": "argon2"}, Argon2HasherConfig),
        ],
    )
    def test_missing_pepper_is_rejected(
        self,
        data: dict[str, str],
        expected: type,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Every hasher build without the env pepper raises ConfigError."""
        monkeypatch.delenv("PIIGHOST_HASH_PEPPER", raising=False)
        config = expected(**data)
        with pytest.raises(ConfigError):
            config.build()

    def test_non_positive_cost_is_rejected(self) -> None:
        """An argon2 cost below one fails validation."""
        invalid_cost: int = 0
        with pytest.raises(ValidationError):
            Argon2HasherConfig(type="argon2", time_cost=invalid_cost)

    def test_union_dispatches_on_type(self) -> None:
        """The type discriminant selects the matching hasher config."""
        adapter = TypeAdapter(HasherConfig)
        assert isinstance(
            adapter.validate_python({"type": "argon2"}), Argon2HasherConfig
        )


class TestCipherConfig:
    def test_aesgcm_builds_with_env_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The aesgcm config builds an AesGcmCipher from the base64 env key."""
        monkeypatch.setenv("PIIGHOST_CIPHER_KEY", _KEY_B64)
        assert isinstance(AesGcmCipherConfig(type="aesgcm").build(), AesGcmCipher)

    def test_missing_key_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A cipher build without the env key raises ConfigError."""
        monkeypatch.delenv("PIIGHOST_CIPHER_KEY", raising=False)
        with pytest.raises(ConfigError):
            AesGcmCipherConfig(type="aesgcm").build()

    def test_invalid_base64_key_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cipher build with a non-base64 key raises ConfigError."""
        monkeypatch.setenv("PIIGHOST_CIPHER_KEY", "not valid base64 !!!")
        with pytest.raises(ConfigError):
            AesGcmCipherConfig(type="aesgcm").build()
