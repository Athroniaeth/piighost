from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Span:
    """Represents the position of a substring within a text.

    Attributes:
        start_pos: Inclusive start index in the source text.
        end_pos: Exclusive end index in the source text.
    """

    start_pos: int
    end_pos: int

    def __post_init__(self) -> None:
        if self.start_pos < 0 or self.end_pos < self.start_pos:
            raise ValueError(
                f"Invalid span bounds: start_pos={self.start_pos}, "
                f"end_pos={self.end_pos} (need 0 <= start_pos <= end_pos)"
            )

    def overlaps(self, other: "Span") -> bool:
        """Check whether this span overlaps with another.

        Args:
            other: The span to test against.

        Returns:
            ``True`` if the two spans share at least one character position.
        """
        return self.start_pos < other.end_pos and other.start_pos < self.end_pos


@dataclass(frozen=True)
class Detection:
    """Represents a named entity recognition (NER) result from a text.

    Attributes:
        text: The surface form found in the source string (e.g. ``"Patrick"``).
            This field holds **raw PII**: it is masked in ``__repr__``; use
            :meth:`to_dict` for the raw value. If you forward Detection
            instances to logs or external sinks, scrub them yourself
            (e.g. via :meth:`to_dict` filtered, or a structured logger
            with field-level redaction).
        label: The entity type (e.g. ``"PERSON"``, ``"LOCATION"``).
        position: The span indicating where the entity was found.
        confidence: Confidence score of the detection (0.0 – 1.0).
    """

    text: str
    label: str
    position: Span
    confidence: float

    def __repr__(self) -> str:
        masked = f"{self.text[:1]}***" if self.text else ""
        return (
            f"Detection(text={masked!r}, label={self.label!r}, "
            f"position={self.position!r}, confidence={self.confidence!r})"
        )

    def to_dict(self, *, redact_as: str | None = None) -> dict[str, Any]:
        """Return a JSON-friendly mapping of this detection.

        Args:
            redact_as: When set, the raw surface ``text`` is replaced by
                this value in the output instead of the real PII. Left to
                ``None`` (the default) the raw text is emitted as-is.

        Why this parameter exists: the very same serialization is needed
        in two places with opposite requirements, and we want a single
        serialization path rather than two divergent ones.

        * The cache stores detections to later restore the original text,
          so it needs the raw ``text`` and calls ``to_dict()`` with no
          argument.
        * The observation layer, when the operator opts into redaction,
          must not let raw PII reach the trace backend, so it passes the
          entity's placeholder token via ``redact_as`` to scrub the text
          while keeping the label, position, and confidence intact.
        """
        text = redact_as or self.text
        return {
            "text": text,
            "label": self.label,
            "start_pos": self.position.start_pos,
            "end_pos": self.position.end_pos,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Detection":
        """Build a Detection from the mapping produced by :meth:`to_dict`."""
        return cls(
            text=data["text"],
            label=data["label"],
            position=Span(
                start_pos=data["start_pos"],
                end_pos=data["end_pos"],
            ),
            confidence=data["confidence"],
        )


@dataclass(frozen=True)
class Entity:
    """Group of detections that refer to the same PII.

    All detections in an entity share the same label. The label is
    derived from the first detection in the list.

    Attributes:
        detections: Tuple of detections referring to the same PII.

    Raises:
        ValueError: If ``detections`` is empty.
    """

    detections: tuple[Detection, ...]

    def __post_init__(self) -> None:
        if not self.detections:
            raise ValueError("At least one detection is required")

    @property
    def label(self) -> str:
        """The entity type, derived from the first detection.

        Returns:
            The label string (e.g. ``"PERSON"``).
        """
        return self.detections[0].label

    @property
    def canonical(self) -> str:
        """Lower-cased canonical surface text (first detection)."""
        return self.detections[0].text.lower()

    @property
    def canonical_key(self) -> tuple[str, str]:
        """Identity key ``(canonical, label)`` used for dedup and cross-message linking."""
        return (self.canonical, self.label)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping of this entity."""
        return {"detections": [d.to_dict() for d in self.detections]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Entity":
        """Build an Entity from the mapping produced by :meth:`to_dict`."""
        return cls(detections=tuple(Detection.from_dict(d) for d in data["detections"]))
