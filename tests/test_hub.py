"""Tests for the hub client: reference parsing, payloads, and the cache."""

from collections.abc import Callable
from pathlib import Path
from typing import Never, Self

import pytest

from piighost.components.detector import RegexDetector
from piighost.hub import (
    DEFAULT_HUB_URL,
    HUB_URL_ENV_VAR,
    HubPayloadError,
    HubRefError,
    HubUnreachableError,
    HubUrlError,
    parse_ref,
    pull,
)

DETECTOR_TOML = r"""# piighost/logs:fd79aec6
[detector]
type = 'regex'

[detector.patterns]
EMAIL = '\S+@\S+'
IPV4 = '\d+\.\d+\.\d+\.\d+'
"""
"""What the hub returns for a group, its rendered detector alone."""

COMPOSITE_TOML = """[detector]
type = 'gliner2'
model = 'fastino/gliner2-multi-v1'
"""
"""A reference whose detector is a model, which carries more than regexes."""

REFS = [
    ("piighost/logs", ("piighost", "logs", "latest")),
    ("piighost/logs:fd79aec6", ("piighost", "logs", "fd79aec6")),
    ("hub:piighost/logs:stable", ("piighost", "logs", "stable")),
    ("  piighost/fr-extended  ", ("piighost", "fr-extended", "latest")),
]
"""Reference, and the namespace, name and selector it splits into."""

BAD_REFS = [
    "logs",
    "piighost/",
    "/logs",
    "piighost/Logs",
    "piighost/logs:Stable",
    "../../etc/passwd",
    "piighost/logs:a b",
]
"""References that must be refused rather than turned into a URL."""


Serve = Callable[[str], list[str]]
"""Install a body for any URL, and hand back the list of URLs asked for."""


class _Answer:
    """The slice of an HTTP response urlopen's caller actually uses."""

    def __init__(self, body: str) -> None:
        self.body = body

    def read(self) -> bytes:
        return self.body.encode("utf-8")

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        return None


@pytest.fixture
def served(monkeypatch: pytest.MonkeyPatch) -> Serve:
    """Serve one body for any URL, and return the list of URLs asked for."""

    def serve(body: str) -> list[str]:
        asked: list[str] = []

        def urlopen(url: str, timeout: float | None = None) -> _Answer:
            asked.append(url)
            return _Answer(body)

        monkeypatch.setattr("piighost.hub.urllib.request.urlopen", urlopen)
        return asked

    return serve


class TestParseRef:
    @pytest.mark.parametrize(("ref", "expected"), REFS)
    def test_splits_a_reference(self, ref: str, expected: tuple[str, str, str]) -> None:
        """A reference splits into its namespace, name and selector."""
        assert parse_ref(ref) == expected

    @pytest.mark.parametrize("ref", BAD_REFS)
    def test_refuses_anything_else(self, ref: str) -> None:
        """A malformed reference raises instead of reaching the network."""
        with pytest.raises(HubRefError):
            parse_ref(ref)


class TestPull:
    def test_returns_the_patterns_in_registry_order(self, served: Serve) -> None:
        """The mapping comes back in the order the registry composed it."""
        served(DETECTOR_TOML)
        assert list(pull("piighost/logs", cache=False)) == ["EMAIL", "IPV4"]

    def test_asks_the_detector_alone_at_the_public_hub(self, served: Serve) -> None:
        """Without configuration it pulls part=detector from the public hub."""
        asked = served(DETECTOR_TOML)
        pull("piighost/logs", cache=False)
        assert asked == [
            (
                f"{DEFAULT_HUB_URL}/api/v1/refs/piighost/logs/latest"
                f"/pipeline.toml?part=detector"
            )
        ]

    def test_the_environment_names_a_private_hub(
        self, served: Serve, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PIIGHOST_HUB_URL redirects every pull to another registry."""
        monkeypatch.setenv(HUB_URL_ENV_VAR, "https://hub.example.com/")
        asked = served(DETECTOR_TOML)
        pull("piighost/logs", cache=False)
        assert asked[0].startswith("https://hub.example.com/api/v1/refs/")

    def test_an_argument_beats_the_environment(
        self, served: Serve, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An explicit hub wins over the environment, for one call."""
        monkeypatch.setenv(HUB_URL_ENV_VAR, "https://hub.example.com")
        asked = served(DETECTOR_TOML)
        pull("piighost/logs", hub="https://other.example.com", cache=False)
        assert asked[0].startswith("https://other.example.com/")

    def test_a_model_detector_is_refused(self, served: Serve) -> None:
        """Taking the regexes out of a model detector would detect less."""
        served(COMPOSITE_TOML)
        with pytest.raises(HubPayloadError, match="gliner2"):
            pull("piighost/ner-base", cache=False)

    def test_a_body_that_is_not_a_detector_is_refused(self, served: Serve) -> None:
        """A payload with no detector raises rather than yielding no pattern."""
        served("name = 'nothing'\n")
        with pytest.raises(HubPayloadError):
            pull("piighost/logs", cache=False)

    @pytest.mark.parametrize("hub", ["file:///etc/passwd", "ftp://x", "nope"])
    def test_a_hub_that_is_not_http_is_refused(self, hub: str) -> None:
        """urlopen speaks file: too, so an origin is checked before it opens."""
        with pytest.raises(HubUrlError):
            pull("piighost/logs", hub=hub, cache=False)

    def test_an_unreachable_hub_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A transport failure surfaces as a hub error, not an OSError."""

        def fail(url: str, timeout: float | None = None) -> Never:
            raise OSError("no route to host")

        monkeypatch.setattr("piighost.hub.urllib.request.urlopen", fail)
        with pytest.raises(HubUnreachableError):
            pull("piighost/logs", cache=False)


class TestCache:
    def test_a_pinned_reference_is_fetched_once(
        self, served: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A commit is immutable, so the second pull reads the disk."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        asked = served(DETECTOR_TOML)
        assert pull("piighost/logs:fd79aec6") == pull("piighost/logs:fd79aec6")
        assert len(asked) == 1

    def test_a_moving_selector_is_never_cached(
        self, served: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """latest moves, and a stale answer would silently detect less."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        asked = served(DETECTOR_TOML)
        pull("piighost/logs")
        pull("piighost/logs")
        assert len(asked) == 2

    def test_the_cache_can_be_turned_off(
        self, served: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """cache=False goes to the hub even for a commit."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        asked = served(DETECTOR_TOML)
        pull("piighost/logs:fd79aec6", cache=False)
        pull("piighost/logs:fd79aec6", cache=False)
        assert len(asked) == 2


class TestFromHub:
    async def test_builds_a_detector_that_detects(
        self, served: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RegexDetector.from_hub returns a detector carrying the reference."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        served(DETECTOR_TOML)
        detector = RegexDetector.from_hub("piighost/logs:fd79aec6")
        found = await detector.detect("mail a@b.co from 10.0.0.1")
        assert {(d.label, d.text) for d in found} == {
            ("EMAIL", "a@b.co"),
            ("IPV4", "10.0.0.1"),
        }
