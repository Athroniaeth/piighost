"""Resolvers: pipeline stages that reconcile detections and entities.

AnyOverlapResolver defines the overlap-resolution port; more resolvers (entity)
will follow.
"""

from piighost.resolver.base import AnyOverlapResolver
from piighost.resolver.overlap import ConfidenceOverlapResolver

__all__ = ["AnyOverlapResolver", "ConfidenceOverlapResolver"]
