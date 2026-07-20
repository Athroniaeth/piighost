"""Anonymizers: replace each entity's spans with its placeholder token.

base.py holds the AnyAnonymizer port and the Anonymization result; concrete
anonymizers live in sibling modules.
"""

from piighost.anonymizer.base import Anonymization, AnyAnonymizer
from piighost.anonymizer.span import Anonymizer

__all__ = ["Anonymization", "AnyAnonymizer", "Anonymizer"]
