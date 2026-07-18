"""Resolvers: pipeline stages that reconcile detections and entities.

base.py holds the abstractions, the AnyOverlapResolver port and the
BaseOverlapResolver template; concrete resolvers live in sibling modules.
"""

from piighost.resolver.base import AnyOverlapResolver, BaseOverlapResolver
from piighost.resolver.confidence import ConfidenceOverlapResolver

__all__ = ["AnyOverlapResolver", "BaseOverlapResolver", "ConfidenceOverlapResolver"]
