"""Pull a detector's regexes from a piighost hub.

A hub is a registry of tested de-identification regexes, addressed by
namespace/name and an optional selector: a tag, or the eight hex characters of
a commit. A reference pinned to a commit is immutable by construction, which
is what makes the on-disk cache safe: the bytes behind piighost/logs:fd79aec6
never change, so they are fetched once and kept. A moving selector is fetched
every time, because serving a stale one would quietly detect less than the
caller asked for.

This module talks HTTP with the standard library alone. The core of piighost
depends on typing-extensions and nothing else, and a registry client is not a
reason to change that.
"""

import hashlib
import os
import re
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from piighost.exceptions import PIIGhostError

DEFAULT_HUB_URL = "https://hub.piighost.dev"
"""The public hub, used when the environment names no other one."""

HUB_URL_ENV_VAR = "PIIGHOST_HUB_URL"
"""Environment variable naming the hub to pull from, for a private registry."""

HUB_SCHEME = "hub:"
"""Optional prefix on a reference, accepted so a config value pastes as is."""

LATEST = "latest"
"""The selector used when a reference carries none: the newest commit."""

TIMEOUT = 10.0
"""Seconds to wait on the hub before giving up, connect and read together."""

ALLOWED_SCHEMES = frozenset({"https", "http"})
"""Schemes a hub origin may use.

urlopen speaks file: and ftp: too, so an origin taken from the environment is
checked before it is opened: PIIGHOST_HUB_URL=file:///etc/passwd would
otherwise turn a pull into a local file read.
"""

_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
"""Kebab-case namespace or object name, the grammar the registry enforces."""

_COMMIT = re.compile(r"^[0-9a-f]{8}$")
"""A selector designating a commit: eight hex characters of its digest."""

_SELECTOR = re.compile(r"^[a-z0-9][a-z0-9-]*$")
"""A selector, which is either a commit or a kebab-case tag."""


class HubError(PIIGhostError):
    """Base class for errors raised while pulling from a hub.

    Catch this to handle any hub failure at once, or catch one of its
    subclasses to react to a specific one.
    """


class HubRefError(HubError):
    """Raised when a reference does not parse as namespace/name with a selector."""


class HubUrlError(HubError):
    """Raised when the hub origin is not an http or https URL."""


class HubUnreachableError(HubError):
    """Raised when the hub cannot be reached or answers with an error status."""


class HubPayloadError(HubError):
    """Raised when the hub answers with something that is not a regex detector.

    The reference resolved, but what came back carries a detector this client
    cannot turn into patterns, a model detector for instance. Taking the
    regexes out of it would detect less than the reference promises, so it
    fails instead.
    """


def pull(ref: str, *, hub: str | None = None, cache: bool = True) -> dict[str, str]:
    """Return the regexes a hub reference carries, keyed by label.

    Args:
        ref: A reference, namespace/name with an optional :selector and an
            optional hub: prefix. Without a selector it resolves to latest.
        hub: Origin of the hub to pull from. Defaults to the environment's
            PIIGHOST_HUB_URL, then to the public hub.
        cache: Whether a commit-pinned reference may be read from and written
            to the on-disk cache. A moving selector is never cached.

    Returns:
        The label to regex mapping, in the order the registry composed it,
        which is the order overlaps are resolved in.

    Raises:
        HubRefError: If the reference does not parse.
        HubUrlError: If the hub origin is not an http or https URL.
        HubUnreachableError: If the hub cannot be reached.
        HubPayloadError: If the answer is not a plain regex detector.
    """
    namespace, name, selector = parse_ref(ref)
    origin = _origin(hub or os.environ.get(HUB_URL_ENV_VAR) or DEFAULT_HUB_URL)
    url = (
        f"{origin}/api/v1/refs/{namespace}/{name}/{selector}"
        f"/pipeline.toml?part=detector"
    )
    pinned = cache and _COMMIT.fullmatch(selector) is not None
    path = _cache_path(url) if pinned else None
    if path is not None and path.exists():
        return _patterns(path.read_text(encoding="utf-8"), ref)

    body = _fetch(url, ref)
    patterns = _patterns(body, ref)
    if path is not None:
        _write_cache(path, body)
    return patterns


def parse_ref(ref: str) -> tuple[str, str, str]:
    """Split a reference into its namespace, name and selector.

    Raises:
        HubRefError: If any of the three is missing or malformed.
    """
    body = ref.removeprefix(HUB_SCHEME).strip()
    key, _, selector = body.partition(":")
    namespace, slash, name = key.partition("/")
    selector = selector or LATEST
    if not slash:
        raise HubRefError(f"{ref!r} is missing the namespace: write namespace/name")
    valid = (
        _NAME.fullmatch(namespace)
        and _NAME.fullmatch(name)
        and _SELECTOR.fullmatch(selector)
    )
    if not valid:
        raise HubRefError(
            f"{ref!r} is not a hub reference: expected namespace/name with an "
            f"optional :tag or :commit, all kebab-case"
        )
    return namespace, name, selector


def _origin(hub: str) -> str:
    """Return the hub origin without its trailing slash, scheme checked.

    Raises:
        HubUrlError: If the scheme is anything but http or https.
    """
    scheme = urllib.parse.urlparse(hub).scheme
    if scheme not in ALLOWED_SCHEMES:
        raise HubUrlError(
            f"{hub!r} is not a hub origin: expected an http or https URL, "
            f"got scheme {scheme or 'none'!r}"
        )
    return hub.rstrip("/")


def _patch_emscripten_transport() -> None:
    """Route urllib through the browser's fetch, once, when running in one.

    Emscripten has no sockets, so urlopen cannot reach the hub from a browser.
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
    """Read the hub's answer as text, turning any transport failure into ours."""
    if sys.platform == "emscripten":
        _patch_emscripten_transport()
    try:
        # The scheme is checked in _origin and the rest of the URL is built
        # from a reference parse_ref has validated, so the open is not blind.
        with urllib.request.urlopen(url, timeout=TIMEOUT) as answer:  # nosec B310
            return answer.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise HubUnreachableError(f"{ref}: the hub answered {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise HubUnreachableError(f"{ref}: cannot reach {url}: {exc}") from exc


def _patterns(body: str, ref: str) -> dict[str, str]:
    """Read the label to regex mapping out of a rendered detector.

    Raises:
        HubPayloadError: If the body is not a TOML regex detector.
    """
    try:
        detector = tomllib.loads(body)["detector"]
    except (tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        raise HubPayloadError(f"{ref}: the hub did not return a detector") from exc
    kind = detector.get("type")
    if kind != "regex" or "patterns" not in detector:
        raise HubPayloadError(
            f"{ref} resolves to a {kind} detector, which carries more than "
            f"regexes; build the whole pipeline from its configuration instead"
        )
    return detector["patterns"]


def _cache_path(url: str) -> Path:
    """Where a pinned reference is kept, named by the digest of its URL.

    The digest rather than the reference, so a hub origin and a reference can
    never collide in the cache and nothing user-supplied reaches the filesystem
    as a path component.
    """
    root = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
    return Path(root) / "piighost" / "hub" / f"{digest}.toml"


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
