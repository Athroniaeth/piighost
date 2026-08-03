"""Reusable regex pattern catalogs for the RegexDetector.

Each catalog is a plain dict mapping a PII label to a regex pattern string.
Combine catalogs by dict merge, for example {**GENERIC_PATTERNS, **FR_PATTERNS}.
"""

from piighost.components.detector.patterns.eu import EU_PATTERNS
from piighost.components.detector.patterns.fr import FR_PATTERNS
from piighost.components.detector.patterns.generic import GENERIC_PATTERNS
from piighost.components.detector.patterns.us import US_PATTERNS

__all__ = ["EU_PATTERNS", "FR_PATTERNS", "GENERIC_PATTERNS", "US_PATTERNS"]
