"""Entity resolver abstractions: the port and a conflict-group template."""

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

from piighost.models import Entity


@runtime_checkable
class AnyEntityResolver(Protocol):
    """A component that reconciles entities into a consistent set.

    Linking can leave entities that should not coexist as they are, such as two
    entities that share a detection, one value split across passes. An entity
    resolver reconciles them, returning a set with those inconsistencies
    resolved.
    """

    def resolve(self, entities: list[Entity]) -> list[Entity]:
        """Return the entities with their inconsistencies reconciled.

        Args:
            entities: The entities to reconcile, possibly sharing detections.

        Returns:
            The reconciled entities.
        """
        ...


class BaseEntityResolver(ABC):
    """Reconcile entities that share detections, one conflict group at a time.

    The skeleton lives here: cluster the entities into groups where each shares
    a detection with another, even transitively, hand each group to the subclass
    to reduce, and collect the results. A subclass defines _reduce, the rule that
    turns a group of entities sharing detections into a consistent set, whether
    by merging them into one or by keeping them apart and giving each shared
    detection to a single entity. Because it sees the whole group, it can weigh
    the entities against each other, not only judge each alone.
    """

    def resolve(self, entities: list[Entity]) -> list[Entity]:
        """Return consistent entities, reducing each conflict group."""
        kept: list[Entity] = []

        for group in self._conflict_groups(entities):
            value = self._reduce(group)
            kept.extend(value)
        return kept

    def _conflict_groups(self, entities: list[Entity]) -> list[list[Entity]]:
        """Cluster entities so each shares a detection with another in its group."""
        groups: list[list[Entity]] = []

        for entity in entities:
            merged = [entity]
            overlapping = [
                group
                for group in groups
                if any(self._shares_detection(entity, member) for member in group)
            ]

            for group in overlapping:
                merged.extend(group)
                groups.remove(group)

            groups.append(merged)

        return groups

    def _shares_detection(self, first: Entity, second: Entity) -> bool:
        """Whether the two entities have at least one detection in common."""
        return not set(first.detections).isdisjoint(second.detections)

    @abstractmethod
    def _reduce(self, conflicting: list[Entity]) -> list[Entity]:
        """Turn a group of entities sharing detections into a consistent set."""
        ...
