"""Detection expander configuration model."""

from typing import Literal

from piighost.components.expander.base import AnyDetectionExpander
from piighost.config.models.common import _ComponentConfig


class WordBoundaryExpanderConfig(_ComponentConfig):
    """Config for the word-boundary expander, adding missed whole-word hits."""

    type: Literal["word_boundary"]
    case_sensitive: bool = False

    def build(self) -> AnyDetectionExpander:
        """Build a WordBoundaryExpander with the configured case sensitivity."""
        from piighost.components.expander.word_boundary import WordBoundaryExpander

        return WordBoundaryExpander(case_sensitive=self.case_sensitive)


ExpanderConfig = WordBoundaryExpanderConfig
"""The expander configuration.

A plain alias while one expander exists; it becomes a discriminated union when a
second expander lands.
"""
