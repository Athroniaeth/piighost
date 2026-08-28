"""Tests for the SQLAlchemy memory config model."""

import pytest

pytest.importorskip("sqlalchemy")

from piighost.config.models.memory import SqlAlchemyMemoryConfig
from piighost.conversation_memory import SqlAlchemyConversationMemory
from piighost.exceptions import ConfigError


class TestBuild:
    def test_builds_from_the_url_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """build reads the database URL from the configured env var."""
        monkeypatch.setenv("PIIGHOST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
        config = SqlAlchemyMemoryConfig(type="sqlalchemy")
        memory = config.build()
        assert isinstance(memory, SqlAlchemyConversationMemory)

    def test_missing_url_env_var_raises_config_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing database URL env var is a configuration error."""
        monkeypatch.delenv("PIIGHOST_DATABASE_URL", raising=False)
        config = SqlAlchemyMemoryConfig(type="sqlalchemy")
        with pytest.raises(ConfigError):
            config.build()

    def test_half_configured_crypto_raises_config_error(self) -> None:
        """Configuring only a hasher (or only a cipher) is a config error."""
        config = SqlAlchemyMemoryConfig(
            type="sqlalchemy",
            hasher={"type": "sha256"},
        )
        with pytest.raises(ConfigError):
            config.build()
