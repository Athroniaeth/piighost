"""Detection expanders: find occurrences a detector missed.

AnyDetectionExpander defines the port; each module provides an adapter.
"""

from piighost.components.expander.base import AnyDetectionExpander
from piighost.components.expander.word_boundary import WordBoundaryExpander

__all__ = ["AnyDetectionExpander", "WordBoundaryExpander"]
