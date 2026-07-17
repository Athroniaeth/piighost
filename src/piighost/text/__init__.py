"""Text utilities shared across the pipeline.

Pure text operations with no external dependency: splitting long text into
offset-aware chunks, and more to come (normalization, patterns).
"""

from piighost.text.splitter import RecursiveCharacterTextSplitter

__all__ = ["RecursiveCharacterTextSplitter"]
