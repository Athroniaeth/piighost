"""Text utilities shared across the pipeline.

Pure text operations with no external dependency: splitting long text into
offset-aware chunks, whole-word search, and the one definition of a space.
"""

from piighost.text.base import AnySplitter
from piighost.text.boundaries import (
    boundary_wrap,
    clear_boundary_cache,
    find_all_word_boundary,
)
from piighost.text.normalization import (
    LINE_SEPARATORS,
    SPACE_SEPARATORS,
    normalize_spaces,
    value_key,
)
from piighost.text.splitter import RecursiveCharacterTextSplitter

__all__ = [
    "LINE_SEPARATORS",
    "SPACE_SEPARATORS",
    "AnySplitter",
    "RecursiveCharacterTextSplitter",
    "boundary_wrap",
    "clear_boundary_cache",
    "find_all_word_boundary",
    "normalize_spaces",
    "value_key",
]
