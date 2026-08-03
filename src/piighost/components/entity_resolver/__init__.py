"""Entity resolvers: reconcile linked entities into a consistent set.

base.py holds the abstractions, the AnyEntityResolver port and the
BaseEntityResolver template; concrete resolvers live in sibling modules.
"""

from piighost.components.entity_resolver.base import (
    AnyEntityResolver,
    BaseEntityResolver,
)
from piighost.components.entity_resolver.merge import MergeEntityResolver
from piighost.components.entity_resolver.separate import SeparateEntityResolver

__all__ = [
    "AnyEntityResolver",
    "BaseEntityResolver",
    "MergeEntityResolver",
    "SeparateEntityResolver",
]
