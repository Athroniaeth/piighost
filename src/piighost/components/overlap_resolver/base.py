"""Resolver abstractions: ports and shared templates for reconciling detections."""

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

from piighost.models import Detection


@runtime_checkable
class AnyOverlapResolver(Protocol):
    """A component that resolves overlapping detections into a clean set.

    Detectors, especially composed or chunked ones, can produce detections
    whose spans overlap. An overlap resolver reconciles them into a set of
    non-overlapping detections.
    """

    def resolve(self, detections: list[Detection]) -> list[Detection]:
        """Return a set of non-overlapping detections.

        Args:
            detections: The detections to reconcile, possibly overlapping.

        Returns:
            The kept detections, none of which overlap another.
        """
        ...


class BaseOverlapResolver(ABC):
    """Resolve overlapping detections one conflict group at a time.

    The skeleton lives here: cluster the detections into groups where each
    overlaps another, hand each group to the subclass to reduce, and return the
    kept detections in position order. A subclass defines _reduce, the rule that
    picks which detections to keep from a group of overlapping ones. Because it
    sees the whole group, it can compare them, not only score each alone.
    """

    def resolve(self, detections: list[Detection]) -> list[Detection]:
        """Return non-overlapping detections, resolving each conflict group."""
        kept: list[Detection] = []
        groups = self._conflict_groups(detections)

        for group in groups:
            reduced = self._reduce(group)
            kept.extend(reduced)
        return sorted(kept)

    def _conflict_groups(self, detections: list[Detection]) -> list[list[Detection]]:
        """Cluster detections so each overlaps at least one other in its group."""
        groups: list[list[Detection]] = []

        for detection in detections:
            merged = [detection]
            overlapping = [
                group
                for group in groups
                if any(detection.overlaps(member) for member in group)
            ]

            for group in overlapping:
                merged.extend(group)
                groups.remove(group)

            groups.append(merged)

        return groups

    @abstractmethod
    def _reduce(self, conflicting: list[Detection]) -> list[Detection]:
        """Pick which non-overlapping detections to keep from an overlap group."""
        ...
