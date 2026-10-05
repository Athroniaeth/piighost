"""Pull a detector's regexes, or a whole configuration, from a piighost catalog.

A catalog is a registry of tested de-identification regexes, addressed by
namespace/name and an optional selector: a tag, or the eight hex characters of
a commit. A reference pinned to a commit is immutable by construction, which
is what makes the on-disk cache safe: the bytes behind piighost/logs:fd79aec6
never change, so they are fetched once and kept. A moving selector is fetched
every time, because serving a stale one would quietly detect less than the
caller asked for.

The catalog is the only source of patterns: piighost ships none of its own, so
two copies of one pattern set cannot drift apart.

Up to 1.x the catalog was called the hub. A reference written hub:namespace/name
and an origin set in PIIGHOST_HUB_URL are still read, so a 1.x config keeps
loading, and piighost.hub re-exports this module under its former names.

This module talks HTTP with the standard library alone. The core of piighost
depends on typing-extensions and nothing else, and a registry client is not a
reason to change that.
"""

import hashlib
import os
import re
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from functools import cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from piighost._runtime import EMSCRIPTEN
from piighost.exceptions import PIIGhostError

DEFAULT_CATALOG_URL = "https://catalog.piighost.dev"
"""The public catalog, used when the environment names no other one."""

CATALOG_URL_ENV_VAR = "PIIGHOST_CATALOG_URL"
"""Environment variable naming the catalog to pull from, for a private registry."""

LEGACY_URL_ENV_VAR = "PIIGHOST_HUB_URL"
"""The variable 1.x read for the same origin, still read when the new one is unset."""

CATALOG_SCHEME = "catalog:"
"""Optional prefix on a reference, accepted so a config value pastes as is."""

LEGACY_SCHEME = "hub:"
"""The prefix 1.x wrote references with, read exactly as catalog: is."""

SCHEMES = (CATALOG_SCHEME, LEGACY_SCHEME)
"""Every prefix that marks a string as a catalog reference rather than a path."""

LATEST = "latest"
"""The selector used when a reference carries none: the newest commit."""

TIMEOUT = 10.0
"""Seconds to wait on the catalog before giving up, connect and read together."""


def _user_agent() -> str:
    """Name the caller piighost/<version>, so the catalog counts its pulls."""
    try:
        return f"piighost/{version('piighost')}"
    except PackageNotFoundError:  # a source checkout without its metadata
        return "piighost"


USER_AGENT = _user_agent()
"""Sent with every request: the catalog tells the library's pulls from a browser's."""

ALLOWED_SCHEMES = frozenset({"https", "http"})
"""Schemes a catalog origin may use.

urlopen speaks file: and ftp: too, so an origin taken from the environment is
checked before it is opened: PIIGHOST_CATALOG_URL=file:///etc/passwd would
otherwise turn a pull into a local file read.
"""

_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
"""Kebab-case namespace or object name, the grammar the registry enforces."""

_COMMIT = re.compile(r"^[0-9a-f]{8}$")
"""A selector designating a commit: eight hex characters of its digest."""

_SELECTOR = re.compile(r"^[a-z0-9][a-z0-9-]*$")
"""A selector, which is either a commit or a kebab-case tag."""


class CatalogError(PIIGhostError):
    """Base class for errors raised while pulling from a catalog.

    Catch this to handle any catalog failure at once, or catch one of its
    subclasses to react to a specific one.
    """


class CatalogRefError(CatalogError):
    """Raised when a reference does not parse as namespace/name with a selector."""


class CatalogUrlError(CatalogError):
    """Raised when the catalog origin is not an http or https URL."""


class CatalogUnreachableError(CatalogError):
    """Raised when the catalog cannot be reached or answers with an error status."""


class CatalogPayloadError(CatalogError):
    """Raised when the catalog answers with something that is not a regex detector.

    The reference resolved, but what came back carries a detector this client
    cannot turn into patterns, a model detector for instance. Taking the
    regexes out of it would detect less than the reference promises, so it
    fails instead.
    """


def pull(ref: str, *, catalog: str | None = None, cache: bool = True) -> dict[str, str]:
    """Return the regexes a catalog reference carries, keyed by label.

    Args:
        ref: A reference, namespace/name with an optional :selector and an
            optional catalog: prefix (hub: from 1.x too). Without a selector it
            resolves to latest.
        catalog: Origin of the catalog to pull from. Defaults to the
            environment's PIIGHOST_CATALOG_URL, then to PIIGHOST_HUB_URL, then
            to the public catalog.
        cache: Whether a commit-pinned reference may be read from and written
            to the on-disk cache. A moving selector is never cached.

    Returns:
        The label to regex mapping, in the order the registry composed it,
        which is the order overlaps are resolved in.

    Raises:
        CatalogRefError: If the reference does not parse.
        CatalogUrlError: If the catalog origin is not an http or https URL.
        CatalogUnreachableError: If the catalog cannot be reached.
        CatalogPayloadError: If the answer is not a plain regex detector.
    """
    body = _read(ref, catalog=catalog, cache=cache, query="?part=detector")
    return _patterns(body, ref)


def pull_config(ref: str, *, catalog: str | None = None, cache: bool = True) -> str:
    """Return the whole pipeline configuration a catalog reference names, as TOML.

    The same reference pull reads for its detector alone. A configuration
    carries every stage, a model detector, the resolvers and a memory
    included, so it is handed to the config loader rather than taken apart
    here.

    Args:
        ref: A reference, namespace/name with an optional :selector and an
            optional catalog: prefix (hub: from 1.x too). Without a selector it
            resolves to latest.
        catalog: Origin of the catalog to pull from. Defaults to the
            environment's PIIGHOST_CATALOG_URL, then to PIIGHOST_HUB_URL, then
            to the public catalog.
        cache: Whether a commit-pinned reference may be read from and written
            to the on-disk cache. A moving selector is never cached.

    Raises:
        CatalogRefError: If the reference does not parse.
        CatalogUrlError: If the catalog origin is not an http or https URL.
        CatalogUnreachableError: If the catalog cannot be reached.
    """
    return _read(ref, catalog=catalog, cache=cache, query="")


def _read(ref: str, *, catalog: str | None, cache: bool, query: str) -> str:
    """Return the pipeline.toml a reference names, through the disk cache.

    The query selects what the catalog renders, the detector alone or the whole
    pipeline, and is part of the URL the cache is keyed by, so the two never
    stand in for each other.
    """
    namespace, name, selector = parse_ref(ref)
    origin = _origin(
        catalog
        or os.environ.get(CATALOG_URL_ENV_VAR)
        or os.environ.get(LEGACY_URL_ENV_VAR)
        or DEFAULT_CATALOG_URL
    )
    url = f"{origin}/api/v1/refs/{namespace}/{name}/{selector}/pipeline.toml{query}"
    pinned = cache and _COMMIT.fullmatch(selector) is not None
    path = _cache_path(url) if pinned else None
    if path is not None and path.exists():
        return path.read_text(encoding="utf-8")

    body = _fetch(url, ref)
    if path is not None:
        _write_cache(path, body)
    return body


def parse_ref(ref: str) -> tuple[str, str, str]:
    """Split a reference into its namespace, name and selector.

    The reference may carry a catalog: prefix, or the hub: prefix 1.x wrote.

    Raises:
        CatalogRefError: If any of the three is missing or malformed.
    """
    scheme = next((prefix for prefix in SCHEMES if ref.startswith(prefix)), "")
    body = ref.removeprefix(scheme).strip()
    key, _, selector = body.partition(":")
    namespace, slash, name = key.partition("/")
    selector = selector or LATEST
    if not slash:
        raise CatalogRefError(f"{ref!r} is missing the namespace: write namespace/name")
    valid = (
        _NAME.fullmatch(namespace)
        and _NAME.fullmatch(name)
        and _SELECTOR.fullmatch(selector)
    )
    if not valid:
        raise CatalogRefError(
            f"{ref!r} is not a catalog reference: expected namespace/name with an "
            f"optional :tag or :commit, all kebab-case"
        )
    return namespace, name, selector


def _origin(catalog: str) -> str:
    """Return the catalog origin without its trailing slash, scheme checked.

    Raises:
        CatalogUrlError: If the scheme is anything but http or https.
    """
    scheme = urllib.parse.urlparse(catalog).scheme
    if scheme not in ALLOWED_SCHEMES:
        raise CatalogUrlError(
            f"{catalog!r} is not a catalog origin: expected an http or https URL, "
            f"got scheme {scheme or 'none'!r}"
        )
    return catalog.rstrip("/")


@cache
def _patch_emscripten_transport() -> None:
    """Route urllib through the browser's fetch, once, when running in one.

    Emscripten has no sockets, so urlopen cannot reach the catalog from a browser.
    pyodide-http replaces urllib's transport with one built on the browser's own
    APIs; it ships with the Pyodide distribution, so this normally succeeds. When
    it is absent the patch is skipped and the open below fails as any transport
    failure does, with the URL in the message.
    """
    try:
        import pyodide_http  # pyrefly: ignore[missing-import]
    except ImportError:
        return
    pyodide_http.patch_all()


def _fetch(url: str, ref: str) -> str:
    """Read the catalog's answer as text, turning any transport failure into ours."""
    if EMSCRIPTEN:
        _patch_emscripten_transport()
    try:
        # The scheme is checked in _origin and the rest of the URL is built
        # from a reference parse_ref has validated, so the open is not blind.
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=TIMEOUT) as answer:  # nosec B310
            return answer.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise CatalogUnreachableError(
            f"{ref}: the catalog answered {exc.code}"
        ) from exc
    except OSError as exc:  # URLError and TimeoutError are both OSError
        raise CatalogUnreachableError(f"{ref}: cannot reach {url}: {exc}") from exc


def _patterns(body: str, ref: str) -> dict[str, str]:
    """Read the label to regex mapping out of a rendered detector.

    Raises:
        CatalogPayloadError: If the body is not a TOML regex detector.
    """
    try:
        detector = tomllib.loads(body)["detector"]
    except (tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        raise CatalogPayloadError(
            f"{ref}: the catalog did not return a detector"
        ) from exc
    kind = detector.get("type")
    if kind != "regex" or "patterns" not in detector:
        raise CatalogPayloadError(
            f"{ref} resolves to a {kind} detector, which carries more than "
            f"regexes; build the whole pipeline from its configuration instead"
        )
    return detector["patterns"]


def _cache_path(url: str) -> Path:
    """Where a pinned reference is kept, named by the digest of its URL.

    The digest rather than the reference, so a catalog origin and a reference
    can never collide in the cache and nothing user-supplied reaches the
    filesystem as a path component. The directory is named catalog: what 1.x
    cached under hub is not read, so a pinned reference is fetched once more.
    """
    root = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
    return Path(root) / "piighost" / "catalog" / f"{digest}.toml"


def _write_cache(path: Path, body: str) -> None:
    """Keep a pinned answer, ignoring a cache that cannot be written.

    A read-only or full home is a reason to go to the network next time, not a
    reason to fail a call that has already succeeded.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    except OSError:
        pass
