"""LlamaIndex integration for PII de-identification in a RAG pipeline.

Needs the llama-index optional dependency (pip install piighost[llama-index]), so
its modules are imported lazily: reaching for a component without the extra raises
a helpful ImportError, while importing this package never pulls llama-index in.
"""

from typing import Any

__all__ = ["PIINodeAnonymizer"]


def __getattr__(name: str) -> Any:
    """Import a component on demand so the optional dependency stays optional."""
    if name == "PIINodeAnonymizer":
        from piighost.integrations.llama_index.transform import PIINodeAnonymizer

        return PIINodeAnonymizer

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
