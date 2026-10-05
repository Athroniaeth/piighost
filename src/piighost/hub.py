"""The 1.x name of piighost.catalog, kept so code written for 1.8 and later runs.

The registry piighost pulls patterns and configurations from was called the hub
up to 1.x and is the catalog since 2.0. This module re-exports piighost.catalog
under the former names: HubError is CatalogError, DEFAULT_HUB_URL is the
catalog's public origin, and pull and pull_config take the origin as hub=
rather than catalog=. New code imports piighost.catalog.
"""

from piighost.catalog import (
    ALLOWED_SCHEMES,
    DEFAULT_CATALOG_URL,
    LATEST,
    LEGACY_SCHEME,
    LEGACY_URL_ENV_VAR,
    TIMEOUT,
    CatalogError,
    CatalogPayloadError,
    CatalogRefError,
    CatalogUnreachableError,
    CatalogUrlError,
    parse_ref,
)
from piighost.catalog import pull as _pull
from piighost.catalog import pull_config as _pull_config

__all__ = [
    "ALLOWED_SCHEMES",
    "DEFAULT_HUB_URL",
    "HUB_SCHEME",
    "HUB_URL_ENV_VAR",
    "LATEST",
    "TIMEOUT",
    "HubError",
    "HubPayloadError",
    "HubRefError",
    "HubUnreachableError",
    "HubUrlError",
    "parse_ref",
    "pull",
    "pull_config",
]

DEFAULT_HUB_URL = DEFAULT_CATALOG_URL
"""The public catalog, under its 1.x name."""

HUB_URL_ENV_VAR = LEGACY_URL_ENV_VAR
"""PIIGHOST_HUB_URL, still read when PIIGHOST_CATALOG_URL is unset."""

HUB_SCHEME = LEGACY_SCHEME
"""The hub: prefix, still read exactly as catalog: is."""

HubError = CatalogError
HubRefError = CatalogRefError
HubUrlError = CatalogUrlError
HubUnreachableError = CatalogUnreachableError
HubPayloadError = CatalogPayloadError


def pull(ref: str, *, hub: str | None = None, cache: bool = True) -> dict[str, str]:
    """Return the regexes a reference carries, as piighost.catalog.pull does.

    Args:
        ref: A reference, with or without its catalog: or hub: prefix.
        hub: Origin of the catalog to pull from, passed on as catalog=.
        cache: Whether a commit-pinned reference may use the on-disk cache.
    """
    return _pull(ref, catalog=hub, cache=cache)


def pull_config(ref: str, *, hub: str | None = None, cache: bool = True) -> str:
    """Return the configuration a reference names, as piighost.catalog.pull_config does.

    Args:
        ref: A reference, with or without its catalog: or hub: prefix.
        hub: Origin of the catalog to pull from, passed on as catalog=.
        cache: Whether a commit-pinned reference may use the on-disk cache.
    """
    return _pull_config(ref, catalog=hub, cache=cache)
