"""PIIGhost: composable PII anonymization pipeline for LLM agents."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("piighost")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree without an installed distribution.
    __version__ = "0.0.0"

__all__ = ["__version__"]
