"""Entity resolvers: reconcile linked entities into a consistent set.

base.py holds the abstractions, the AnyEntityResolver port and the
BaseEntityResolver template; concrete resolvers live in sibling modules.
FuzzyEntityResolver needs the rapidfuzz optional dependency, so it is imported
lazily: reaching for it without the extra raises a helpful ImportError, while
importing this package never pulls rapidfuzz in.
"""

from typing import Any

from piighost.components.entity_resolver.base import (
    AnyEntityResolver,
    BaseEntityResolver,
)
from piighost.components.entity_resolver.merge import MergeEntityResolver
from piighost.components.entity_resolver.separate import SeparateEntityResolver

__all__ = [
    "AnyEntityResolver",
    "BaseEntityResolver",
    "FuzzyEntityResolver",
    "MergeEntityResolver",
    "SeparateEntityResolver",
]


def __getattr__(name: str) -> Any:
    """Import FuzzyEntityResolver on demand so its optional extra stays optional."""
    if name == "FuzzyEntityResolver":
        from piighost.components.entity_resolver.fuzzy import FuzzyEntityResolver

        return FuzzyEntityResolver

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
