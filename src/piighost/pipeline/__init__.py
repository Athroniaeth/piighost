"""Pipelines: chain the anonymization stages into a single use case.

base.py holds AnonymizationPipeline, the one-text pipeline; thread-aware
pipelines live in sibling modules.
"""

from piighost.pipeline.base import AnonymizationPipeline

__all__ = ["AnonymizationPipeline"]
