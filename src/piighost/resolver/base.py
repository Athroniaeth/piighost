"""Resolver ports: contracts for reconciling detections and entities."""

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
