"""Domain data models.

The primary value objects the pipeline operates on. Pure Python, frozen,
no external dependencies, so they stay trivially testable.
"""

from piighost.models.span import Span

__all__ = ["Span"]
