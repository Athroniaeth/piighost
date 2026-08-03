"""Detection expanders: find occurrences a detector missed.

base.py holds the AnyDetectionExpander port and the BaseDetectionExpander
template; concrete expanders live in sibling modules.
"""

from piighost.components.expander.base import (
    AnyDetectionExpander,
    BaseDetectionExpander,
)
from piighost.components.expander.word_boundary import WordBoundaryExpander

__all__ = [
    "AnyDetectionExpander",
    "BaseDetectionExpander",
    "WordBoundaryExpander",
]
