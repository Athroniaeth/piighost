"""Tests for the Argon2id hasher and its optional-dependency guard."""

import importlib
import importlib.util
import sys
from typing import Any

import pytest

_MODULE = "piighost.crypto.hasher.argon2id"


class TestOptionalDependencyGuard:
    def test_missing_argon2_explains_how_to_install(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Importing without argon2-cffi points the user at piighost[argon2]."""
        real_find_spec = importlib.util.find_spec

        def find_spec(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "argon2":
                return None
            return real_find_spec(name, *args, **kwargs)

        monkeypatch.setattr(importlib.util, "find_spec", find_spec)
        sys.modules.pop(_MODULE, None)

        with pytest.raises(ImportError, match=r"piighost\[argon2\]"):
            importlib.import_module(_MODULE)

        sys.modules.pop(_MODULE, None)


class TestUsableWhenInstalled:
    def test_conforms_to_the_port(self) -> None:
        """With argon2-cffi installed, Argon2Hasher is an AnyHasher."""
        pytest.importorskip("argon2")
        from piighost.crypto.hasher import AnyHasher, Argon2Hasher

        assert isinstance(Argon2Hasher("pepper-secret"), AnyHasher)

    def test_installed_argon2_hashes_deterministically(self) -> None:
        """A digest is a 64-char hex string and stable across calls."""
        pytest.importorskip("argon2")
        from piighost.crypto.hasher import Argon2Hasher

        hasher = Argon2Hasher("pepper-secret")
        digest = hasher.hash("Emma")
        assert len(digest) == 64
        assert bytes.fromhex(digest)
        assert hasher.hash("Emma") == digest

    def test_distinct_values_differ(self) -> None:
        """Different values hash to different digests."""
        pytest.importorskip("argon2")
        from piighost.crypto.hasher import Argon2Hasher

        hasher = Argon2Hasher("pepper-secret")
        assert hasher.hash("Emma") != hasher.hash("Liam")

    def test_pepper_keys_the_digest(self) -> None:
        """The same value under different peppers hashes differently."""
        pytest.importorskip("argon2")
        from piighost.crypto.hasher import Argon2Hasher

        assert Argon2Hasher("one").hash("Emma") != Argon2Hasher("two").hash("Emma")

    def test_empty_pepper_is_rejected(self) -> None:
        """Argon2Hasher inherits the fail-closed empty-pepper guard."""
        pytest.importorskip("argon2")
        from piighost.exceptions import EmptyPepperError
        from piighost.crypto.hasher import Argon2Hasher

        with pytest.raises(EmptyPepperError):
            Argon2Hasher("")

    def test_hash_length_is_configurable(self) -> None:
        """A custom hash length sizes the digest, hex being twice the bytes."""
        pytest.importorskip("argon2")
        from piighost.crypto.hasher import Argon2Hasher

        assert len(Argon2Hasher("pepper-secret", hash_length=16).hash("Emma")) == 32

    def test_cost_parameters_change_the_digest(self) -> None:
        """A different Argon2 cost yields a different digest for the same input."""
        pytest.importorskip("argon2")
        from piighost.crypto.hasher import Argon2Hasher

        cheap = Argon2Hasher("pepper-secret", time_cost=1).hash("Emma")
        dearer = Argon2Hasher("pepper-secret", time_cost=3).hash("Emma")
        assert cheap != dearer
