"""Tests for the catalog client: reference parsing, payloads, and the cache."""

from collections.abc import Callable
from pathlib import Path
from typing import Never, Self

import pytest

from piighost.catalog import (
    CATALOG_URL_ENV_VAR,
    DEFAULT_CATALOG_URL,
    LEGACY_URL_ENV_VAR,
    CatalogPayloadError,
    CatalogRefError,
    CatalogUnreachableError,
    CatalogUrlError,
    parse_ref,
    pull,
    pull_config,
)
from piighost.components.detector import RegexDetector

DETECTOR_TOML = r"""# piighost/logs:fd79aec6
[detector]
type = 'regex'

[detector.patterns]
EMAIL = '\S+@\S+'
IPV4 = '\d+\.\d+\.\d+\.\d+'
"""
"""What the catalog returns for a group, its rendered detector alone."""

COMPOSITE_TOML = """[detector]
type = 'gliner2'
model = 'fastino/gliner2-multi-v1'
"""
"""A reference whose detector is a model, which carries more than regexes."""

PIPELINE_TOML = r"""name = 'piighost/notarial:2f602547'

[detector]
type = 'regex'

[detector.patterns]
EMAIL = '\S+@\S+'

[overlap_resolver]
type = 'merge'
"""
"""What the catalog returns for a whole configuration, every stage included."""

REFS = [
    ("piighost/logs", ("piighost", "logs", "latest")),
    ("piighost/logs:fd79aec6", ("piighost", "logs", "fd79aec6")),
    ("catalog:piighost/logs:stable", ("piighost", "logs", "stable")),
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
    "catalog:hub:piighost/logs",
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

        monkeypatch.setattr("piighost.catalog.urllib.request.urlopen", urlopen)
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
        with pytest.raises(CatalogRefError):
            parse_ref(ref)


class TestPull:
    def test_returns_the_patterns_in_registry_order(self, served: Serve) -> None:
        """The mapping comes back in the order the registry composed it."""
        served(DETECTOR_TOML)
        assert list(pull("piighost/logs", cache=False)) == ["EMAIL", "IPV4"]

    def test_asks_the_detector_alone_at_the_public_catalog(self, served: Serve) -> None:
        """Without configuration it pulls part=detector from the public catalog."""
        asked = served(DETECTOR_TOML)
        pull("piighost/logs", cache=False)
        assert asked == [
            (
                f"{DEFAULT_CATALOG_URL}/api/v1/refs/piighost/logs/latest"
                f"/pipeline.toml?part=detector"
            )
        ]

    def test_the_environment_names_a_private_catalog(
        self, served: Serve, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PIIGHOST_CATALOG_URL redirects every pull to another registry."""
        monkeypatch.setenv(CATALOG_URL_ENV_VAR, "https://catalog.example.com/")
        asked = served(DETECTOR_TOML)
        pull("piighost/logs", cache=False)
        assert asked[0].startswith("https://catalog.example.com/api/v1/refs/")

    def test_the_1x_variable_is_still_read(
        self, served: Serve, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PIIGHOST_HUB_URL, set for 1.x, still names the registry."""
        monkeypatch.delenv(CATALOG_URL_ENV_VAR, raising=False)
        monkeypatch.setenv(LEGACY_URL_ENV_VAR, "https://legacy.example.com")
        asked = served(DETECTOR_TOML)
        pull("piighost/logs", cache=False)
        assert asked[0].startswith("https://legacy.example.com/api/v1/refs/")

    def test_the_new_variable_beats_the_1x_one(
        self, served: Serve, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With both set, PIIGHOST_CATALOG_URL wins."""
        monkeypatch.setenv(CATALOG_URL_ENV_VAR, "https://catalog.example.com")
        monkeypatch.setenv(LEGACY_URL_ENV_VAR, "https://legacy.example.com")
        asked = served(DETECTOR_TOML)
        pull("piighost/logs", cache=False)
        assert asked[0].startswith("https://catalog.example.com/")

    def test_an_argument_beats_the_environment(
        self, served: Serve, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An explicit catalog wins over the environment, for one call."""
        monkeypatch.setenv(CATALOG_URL_ENV_VAR, "https://catalog.example.com")
        asked = served(DETECTOR_TOML)
        pull("piighost/logs", catalog="https://other.example.com", cache=False)
        assert asked[0].startswith("https://other.example.com/")

    def test_a_model_detector_is_refused(self, served: Serve) -> None:
        """Taking the regexes out of a model detector would detect less."""
        served(COMPOSITE_TOML)
        with pytest.raises(CatalogPayloadError, match="gliner2"):
            pull("piighost/ner-base", cache=False)

    def test_a_body_that_is_not_a_detector_is_refused(self, served: Serve) -> None:
        """A payload with no detector raises rather than yielding no pattern."""
        served("name = 'nothing'\n")
        with pytest.raises(CatalogPayloadError):
            pull("piighost/logs", cache=False)

    @pytest.mark.parametrize("catalog", ["file:///etc/passwd", "ftp://x", "nope"])
    def test_a_catalog_that_is_not_http_is_refused(self, catalog: str) -> None:
        """urlopen speaks file: too, so an origin is checked before it opens."""
        with pytest.raises(CatalogUrlError):
            pull("piighost/logs", catalog=catalog, cache=False)

    def test_an_unreachable_catalog_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A transport failure surfaces as a catalog error, not an OSError."""

        def fail(url: str, timeout: float | None = None) -> Never:
            raise OSError("no route to host")

        monkeypatch.setattr("piighost.catalog.urllib.request.urlopen", fail)
        with pytest.raises(CatalogUnreachableError):
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

    def test_the_cache_lives_under_catalog(
        self, served: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A pinned answer is kept in piighost/catalog, not in the 1.x hub folder."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        served(DETECTOR_TOML)
        pull("piighost/logs:fd79aec6")
        assert len(list((tmp_path / "piighost" / "catalog").iterdir())) == 1
        assert not (tmp_path / "piighost" / "hub").exists()

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
        """cache=False goes to the catalog even for a commit."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        asked = served(DETECTOR_TOML)
        pull("piighost/logs:fd79aec6", cache=False)
        pull("piighost/logs:fd79aec6", cache=False)
        assert len(asked) == 2


class TestFromCatalog:
    async def test_builds_a_detector_that_detects(
        self, served: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RegexDetector.from_catalog returns a detector carrying the reference."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        served(DETECTOR_TOML)
        detector = RegexDetector.from_catalog("catalog:piighost/logs:fd79aec6")
        found = await detector.detect("mail a@b.co from 10.0.0.1")
        assert {(d.label, d.text) for d in found} == {
            ("EMAIL", "a@b.co"),
            ("IPV4", "10.0.0.1"),
        }


class TestPullConfig:
    def test_asks_the_whole_pipeline(self, served: Serve) -> None:
        """A configuration is the whole pipeline.toml, not its detector part."""
        asked = served(PIPELINE_TOML)
        body = pull_config("piighost/notarial:2f602547", cache=False)
        assert body == PIPELINE_TOML
        assert asked == [
            f"{DEFAULT_CATALOG_URL}/api/v1/refs/piighost/notarial/2f602547/pipeline.toml"
        ]

    def test_a_pinned_configuration_is_fetched_once(
        self, served: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A commit is immutable, so the second pull reads the disk."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        asked = served(PIPELINE_TOML)
        pull_config("piighost/notarial:2f602547")
        pull_config("piighost/notarial:2f602547")
        assert len(asked) == 1

    def test_a_detector_and_a_configuration_are_cached_apart(
        self, served: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """One reference read both ways is two answers, never one for the other."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        asked = served(PIPELINE_TOML)
        pull("piighost/notarial:2f602547")
        pull_config("piighost/notarial:2f602547")
        assert len(asked) == 2


class TestHubCompatibility:
    """Code written for 1.8 and later, against piighost.hub, keeps running."""

    def test_the_hub_module_re_exports_the_catalog(self) -> None:
        """Every 1.x name is the catalog object it was renamed to."""
        from piighost import catalog, hub

        assert hub.HubError is catalog.CatalogError
        assert hub.HubRefError is catalog.CatalogRefError
        assert hub.HubUrlError is catalog.CatalogUrlError
        assert hub.HubUnreachableError is catalog.CatalogUnreachableError
        assert hub.HubPayloadError is catalog.CatalogPayloadError
        assert hub.parse_ref is catalog.parse_ref
        assert hub.DEFAULT_HUB_URL == catalog.DEFAULT_CATALOG_URL
        assert hub.HUB_URL_ENV_VAR == "PIIGHOST_HUB_URL"
        assert hub.HUB_SCHEME == "hub:"

    def test_hub_pull_passes_its_origin_on(self, served: Serve) -> None:
        """piighost.hub.pull still takes the origin as hub=."""
        from piighost.hub import pull as hub_pull

        asked = served(DETECTOR_TOML)
        assert list(hub_pull("hub:piighost/logs", hub="https://x.example.com")) == [
            "EMAIL",
            "IPV4",
        ]
        assert asked[0].startswith("https://x.example.com/api/v1/refs/piighost/logs/")

    def test_hub_pull_config_passes_its_origin_on(self, served: Serve) -> None:
        """piighost.hub.pull_config still takes the origin as hub=."""
        from piighost.hub import pull_config as hub_pull_config

        asked = served(PIPELINE_TOML)
        body = hub_pull_config(
            "piighost/notarial:2f602547", hub="https://x.example.com", cache=False
        )
        assert body == PIPELINE_TOML
        assert asked[0].startswith("https://x.example.com/")

    async def test_from_hub_is_from_catalog(self, served: Serve) -> None:
        """RegexDetector.from_hub builds what from_catalog builds, hub= included."""
        asked = served(DETECTOR_TOML)
        detector = RegexDetector.from_hub(
            "hub:piighost/logs", hub="https://x.example.com"
        )
        assert list(detector.patterns) == ["EMAIL", "IPV4"]
        assert asked[0].startswith("https://x.example.com/")
