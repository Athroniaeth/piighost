"""Detectors: components that find PII in text.

AnyDetector defines the port; each module provides an adapter.
"""

from piighost.detector.base import AnyDetector
from piighost.detector.exact import ExactMatchDetector

__all__ = ["AnyDetector", "ExactMatchDetector"]
