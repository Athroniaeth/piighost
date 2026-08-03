"""Pipelines: chain the anonymization stages into a single use case.

base.py holds AnonymizationPipeline, the one-text pipeline; thread-aware
pipelines live in sibling modules.
"""

from piighost.pipeline.base import (
    AnonymizationPipeline,
    AnyPipeline,
    BaseAnonymizationPipeline,
)
from piighost.pipeline.thread import ThreadAnonymizationPipeline

__all__ = [
    "AnonymizationPipeline",
    "AnyPipeline",
    "BaseAnonymizationPipeline",
    "ThreadAnonymizationPipeline",
]
