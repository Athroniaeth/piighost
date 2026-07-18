"""Text utilities shared across the pipeline.

Pure text operations with no external dependency: splitting long text into
offset-aware chunks, and more to come (normalization, patterns).
"""

from piighost.text.base import AnySplitter
from piighost.text.boundaries import boundary_wrap, find_all_word_boundary
from piighost.text.splitter import RecursiveCharacterTextSplitter

__all__ = [
    "AnySplitter",
    "RecursiveCharacterTextSplitter",
    "boundary_wrap",
    "find_all_word_boundary",
]
