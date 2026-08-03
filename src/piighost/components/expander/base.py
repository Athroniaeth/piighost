"""Detection expander port: the contract for finding missed occurrences."""

from typing import Protocol, runtime_checkable

from piighost.models import Detection


@runtime_checkable
class AnyDetectionExpander(Protocol):
    """A component that finds occurrences a detector missed.

    Given the detections found so far and the source text, it returns them plus
    new detections for occurrences of the same values that were not detected.
    This is useful when a NER misses a repeat of a name it flagged elsewhere.
    """

    def expand(self, text: str, detections: list[Detection]) -> list[Detection]:
        """Return the detections plus any missed occurrences of their values.

        Args:
            text: The source text the detections were found in.
            detections: The detections found so far.

        Returns:
            The original detections plus one for each missed occurrence.
        """
        ...
