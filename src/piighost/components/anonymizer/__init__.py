"""Anonymizers: replace each entity's spans with its placeholder token.

base.py holds the AnyAnonymizer port, the BaseAnonymizer template, and the
Anonymization result; concrete anonymizers live in sibling modules.
"""

from piighost.components.anonymizer.base import (
    Anonymization,
    AnyAnonymizer,
    BaseAnonymizer,
)
from piighost.components.anonymizer.span import Anonymizer

__all__ = ["Anonymization", "Anonymizer", "AnyAnonymizer", "BaseAnonymizer"]
