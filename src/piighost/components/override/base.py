"""Detection override abstractions: the port for server-imposed lists."""

from typing import Protocol, runtime_checkable

from piighost.models import Detection


@runtime_checkable
class AnyDetectionOverride(Protocol):
    """A component imposing server decisions on a detection set.

    It is applied right after detection, before overlap resolution and linking,
    and at the memory write points of the thread pipeline, so its decisions
    trump both the detector's output and a human's corrected set. There is no
    Base template: implementations would differ by their whole mechanism, not
    by a single hook, the same pairwise exception as the guard rails.
    """

    async def apply(self, text: str, detections: list[Detection]) -> list[Detection]:
        """Return the detections with the server lists imposed.

        Args:
            text: The message the detections were found in.
            detections: The detections to correct, from any origin.

        Returns:
            The corrected detections, in position order.
        """
        ...

    async def cleared_values(self, text: str) -> frozenset[str]:
        """Return the casefolded values the blacklist matches in this text.

        The pipeline exempts them from the guard rail: a blacklisted value is
        deliberately left in clear, so a detector-based guard would otherwise
        re-find it and refuse the output.

        Args:
            text: The message to scan with the blacklist.

        Returns:
            The casefolded matched values, empty without a blacklist.
        """
        ...
