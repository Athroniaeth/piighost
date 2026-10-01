"""LlamaIndex integration for PII de-identification in a RAG pipeline.

Needs the llama-index optional dependency (pip install piighost[llama-index]), so
its modules are imported lazily: reaching for a component without the extra raises
a helpful ImportError, while importing this package never pulls llama-index in.
"""

import importlib
from typing import Any

__all__ = ["PIINodeAnonymizer", "PIIQueryEngine"]


_LAZY_COMPONENTS: dict[str, str] = {
    "PIINodeAnonymizer": "piighost.integrations.llama_index.transform",
    "PIIQueryEngine": "piighost.integrations.llama_index.query_engine",
}
"""Each component that needs llama-index, by name, with the module that holds it."""


def __getattr__(name: str) -> Any:
    """Import a component on demand so the optional dependency stays optional."""
    if name not in _LAZY_COMPONENTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(_LAZY_COMPONENTS[name]), name)
