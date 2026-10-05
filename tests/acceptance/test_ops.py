"""Acceptance tests of the operator's stories, through public entry points.

Each test carries the id of the acceptance test it implements, AT-<story>-<n>,
the same in every language of the documentation. Redis is fakeredis, one
server shared by every instance a test builds.
"""

from pathlib import Path
from typing import Any

import pytest

from piighost.components.detector import ExactMatchDetector
from piighost.config import load_thread_pipeline
from piighost.exceptions import ConfigError
from piighost.pipeline import ThreadAnonymizationPipeline

_AES_KEY = bytes(range(32))
"""A fixed 256-bit key, so both instances read what the other wrote."""

CIPHER_KEY = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="
"""_AES_KEY in base64, as PIIGHOST_CIPHER_KEY carries it."""

REDIS_TOML = """
[detector]
type = "exact"
values = { Emma = "PERSON" }

[memory]
type = "redis"
url = "redis://redis.invalid:6379/0"

[memory.hasher]
type = "sha256"

[memory.cipher]
type = "aesgcm"
"""
"""A full Redis config, hasher and cipher included, whose secrets come from the env."""


def _instance(server: Any) -> ThreadAnonymizationPipeline:
    """Build one instance of the service over the shared Redis server."""
    import fakeredis.aioredis

    from piighost.conversation_memory import RedisConversationMemory
    from piighost.crypto.cipher import AesGcmCipher
    from piighost.crypto.hasher import Sha256Hasher

    client = fakeredis.aioredis.FakeRedis(server=server)
    memory = RedisConversationMemory(
        client, Sha256Hasher("pepper"), AesGcmCipher(_AES_KEY)
    )
    detector = ExactMatchDetector({"Emma": "PERSON", "Liam": "PERSON"})
    return ThreadAnonymizationPipeline(detector, memory=memory)


class TestSharedMemory:
    async def test_two_instances_agree_on_a_thread(self) -> None:
        """Two instances on one Redis issue and restore the same tokens (AT-OPS-2-1)."""
        fakeredis = pytest.importorskip("fakeredis")
        server = fakeredis.FakeServer()
        first, second = _instance(server), _instance(server)

        assert (await first.anonymize("Hi Emma", "t1")).text == "Hi <<PERSON:1>>"
        assert (await second.anonymize("Bye Emma", "t1")).text == "Bye <<PERSON:1>>"
        assert await second.deanonymize("<<PERSON:1>>", "t1") == "Emma"

        assert (await second.anonymize("And Liam", "t1")).text == "And <<PERSON:2>>"
        assert await first.deanonymize("<<PERSON:2>>", "t1") == "Liam"


class TestSecretsFromTheEnvironment:
    @pytest.mark.parametrize(
        "present",
        [{}, {"PIIGHOST_HASH_PEPPER": "pepper"}, {"PIIGHOST_CIPHER_KEY": CIPHER_KEY}],
    )
    def test_a_full_redis_config_without_its_secrets_does_not_build(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, present: dict[str, str]
    ) -> None:
        """A missing pepper or key stops the build instead of storing in clear (AT-OPS-3-1, AT-DPO-5-2)."""
        pytest.importorskip("redis")
        for name in ("PIIGHOST_HASH_PEPPER", "PIIGHOST_CIPHER_KEY"):
            monkeypatch.delenv(name, raising=False)
        for name, value in present.items():
            monkeypatch.setenv(name, value)
        path = tmp_path / "pipeline.toml"
        path.write_text(REDIS_TOML)

        with pytest.raises(ConfigError, match="PIIGHOST_"):
            load_thread_pipeline(path)

    def test_the_same_config_builds_with_its_secrets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With the pepper and the key set, the same config builds a thread pipeline."""
        pytest.importorskip("redis")
        monkeypatch.setenv("PIIGHOST_HASH_PEPPER", "pepper")
        monkeypatch.setenv("PIIGHOST_CIPHER_KEY", CIPHER_KEY)
        path = tmp_path / "pipeline.toml"
        path.write_text(REDIS_TOML)

        assert isinstance(load_thread_pipeline(path), ThreadAnonymizationPipeline)
