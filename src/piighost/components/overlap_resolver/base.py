"""Resolver abstractions: ports and shared templates for reconciling detections."""

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

from piighost.components._groups import connected_groups
from piighost.models import Detection, Span


def by_confidence(detection: Detection) -> tuple[float, Span]:
    """Sort key ordering detections most confident first, then by position.

    A stable sort on it keeps the earliest detector's detection on a true tie,
    since a conflict group is in detector order.
    """
    return -detection.confidence, detection.span


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
        groups = self._conflict_groups(detections)
        return sorted(kept for group in groups for kept in self._reduce(group))

    def _conflict_groups(self, detections: list[Detection]) -> list[list[Detection]]:
        """Cluster detections so each overlaps at least one other in its group.

        Each returned group is in the input order of its detections. That order
        carries the detector order (a CompositeDetector concatenates its children
        in order), so a subclass that reduces a group with a stable sort keeps the
        earliest detector's detection on a true tie.
        """
        groups = connected_groups(detections, Detection.overlaps)
        return [[detections[index] for index in sorted(group)] for group in groups]

    @abstractmethod
    def _reduce(self, conflicting: list[Detection]) -> list[Detection]:
        """Pick which non-overlapping detections to keep from an overlap group."""
        ...
