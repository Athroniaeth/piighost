"""Span-based text replacement with reversible mappings."""

from maskara.span_replacer.models import Span, ReplacementResult
from maskara.span_replacer.validator import SpanValidator, DefaultSpanValidator
from maskara.span_replacer.replacer import SpanReplacer

__all__ = [
    "Span",
    "ReplacementResult",
    "SpanValidator",
    "DefaultSpanValidator",
    "SpanReplacer",
]
