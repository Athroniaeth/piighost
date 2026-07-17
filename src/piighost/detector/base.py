"""Detector port: the contract every detector adapter satisfies."""

from typing import Protocol, runtime_checkable

from piighost.models import Detection


@runtime_checkable
class AnyDetector(Protocol):
    """A component that finds PII detections in a text.

    Implementations may be regex, NER, or LLM based. detect is async so an
    implementation can await I/O, such as a model server or an LLM API,
    without blocking the pipeline.
    """

    async def detect(self, text: str) -> list[Detection]:
        """Return the detections found in text.

        Args:
            text: The text to scan.

        Returns:
            The detections found, in any order. Overlaps and duplicates are
            resolved by later pipeline stages, not here.
        """
        ...
