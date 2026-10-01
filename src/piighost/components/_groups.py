"""Clustering shared by the two resolvers: group items related to each other."""

from collections.abc import Callable, Sequence
from typing import TypeVar

T = TypeVar("T")
"""The kind of item grouped, a detection or an entity."""


def connected_groups(
    items: Sequence[T], related: Callable[[T, T], bool]
) -> list[list[int]]:
    """Return the indices of items grouped so each relates to another, transitively.

    Each item opens a group and absorbs every earlier group holding an item it
    relates to. A group lists the newest item first, then the members of the
    groups it absorbed, and the groups are in the order they were last formed.
    """
    groups: list[list[int]] = []
    for index, item in enumerate(items):
        merged = [index]
        for group in [g for g in groups if any(related(item, items[i]) for i in g)]:
            merged.extend(group)
            groups.remove(group)
        groups.append(merged)
    return groups
