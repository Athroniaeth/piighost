"""Detectors: components that find PII in text.

AnyDetector defines the port; each module provides an adapter.
"""

from piighost.components.detector.base import AnyDetector
from piighost.components.detector.chunked import ChunkedDetector
from piighost.components.detector.exact import ExactMatchDetector

__all__ = ["AnyDetector", "ChunkedDetector", "ExactMatchDetector"]
