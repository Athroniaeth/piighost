"""Detectors: components that find PII in text.

AnyDetector defines the port; each module provides an adapter. The pure
detectors import eagerly; LLMDetector needs the llm extra, so it is exposed
lazily and never pulled in by importing this package.
"""

from typing import Any

from piighost.components.detector.base import AnyDetector
from piighost.components.detector.chunked import ChunkedDetector
from piighost.components.detector.composite import CompositeDetector
from piighost.components.detector.exact import ExactMatchDetector
from piighost.components.detector.regex import RegexDetector

__all__ = [
    "AnyDetector",
    "ChunkedDetector",
    "CompositeDetector",
    "ExactMatchDetector",
    "LLMDetector",
    "RegexDetector",
]


def __getattr__(name: str) -> Any:
    """Import LLMDetector on demand so its optional extra stays optional."""
    if name == "LLMDetector":
        from piighost.components.detector.llm import LLMDetector

        return LLMDetector

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
