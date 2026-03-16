"""Data models for the anonymization pipeline."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DetectedEntity:
    """A single entity detected by an extractor.

    Attributes:
        text: The surface form found in the source string.
        label: The entity type (e.g. ``"person"``, ``"location"``).
        start: Inclusive start index in the source text.
        end: Exclusive end index in the source text.
        confidence: Model confidence score in ``[0, 1]``.
    """

    text: str
    label: str
    start: int
    end: int
    confidence: float
