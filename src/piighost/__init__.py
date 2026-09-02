"""PIIGhost: composable PII anonymization pipeline for LLM agents.

The core building blocks are re-exported lazily from the top-level package, so
``from piighost import AnonymizationPipeline`` works without importing any optional
extra. Each name is resolved to its home module on first access, so touching the
facade never pulls in torch, langchain, or another heavy dependency.
"""

import importlib
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("piighost")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree without an installed distribution.
    __version__ = "0.0.0"

_LAZY_EXPORTS: dict[str, str] = {
    "AnonymizationPipeline": "piighost.pipeline",
    "ThreadAnonymizationPipeline": "piighost.pipeline",
    "Anonymizer": "piighost.components.anonymizer",
    "ExactMatchDetector": "piighost.components.detector",
    "RegexDetector": "piighost.components.detector",
    "CompositeDetector": "piighost.components.detector",
    "ChunkedDetector": "piighost.components.detector",
    "LabelCounterPlaceholderFactory": "piighost.components.placeholder",
    "LabelHashPlaceholderFactory": "piighost.components.placeholder",
    "Detection": "piighost.models",
    "Entity": "piighost.models",
    "Span": "piighost.models",
    "PIIGhostError": "piighost.exceptions",
}
"""Core symbols re-exported from the package root, each mapped to its home module."""

__all__ = [
    "AnonymizationPipeline",
    "Anonymizer",
    "ChunkedDetector",
    "CompositeDetector",
    "Detection",
    "Entity",
    "ExactMatchDetector",
    "LabelCounterPlaceholderFactory",
    "LabelHashPlaceholderFactory",
    "PIIGhostError",
    "RegexDetector",
    "Span",
    "ThreadAnonymizationPipeline",
    "__version__",
]


def __getattr__(name: str) -> object:
    """Resolve a lazily re-exported core symbol to its home module on first access."""
    module_path = _LAZY_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(module_path)
    return getattr(module, name)


def __dir__() -> list[str]:
    """List the package attributes, including the lazily re-exported core symbols."""
    return sorted(__all__)
