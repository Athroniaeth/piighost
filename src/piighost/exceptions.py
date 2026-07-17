"""PIIGhost exception hierarchy.

Every error the library raises derives from PIIGhostError, so a caller can
catch the whole family with a single except PIIGhostError. Specialized
subclasses let a caller react to one specific failure.
"""


class PIIGhostError(Exception):
    """Base class for every error raised by PIIGhost."""


class SpanError(PIIGhostError):
    """Base class for errors raised while constructing a Span.

    Catch this to handle any invalid-span case at once, or catch one of its
    subclasses to react to a specific violation.
    """


class NegativeSpanStartError(SpanError):
    """Raised when a Span is given a negative start offset."""


class SpanOrderingError(SpanError):
    """Raised when a Span's end is not strictly greater than its start, which
    describes an empty range (end equals start) or a reversed one (end below
    start).
    """


class DetectionError(PIIGhostError):
    """Base class for errors raised while constructing a Detection.

    Catch this to handle any invalid-detection case at once, or catch one of
    its subclasses to react to a specific violation.
    """


class ConfidenceError(DetectionError):
    """Raised when a Detection confidence is outside the range [0, 1]."""


class EntityError(PIIGhostError):
    """Base class for errors raised while constructing an Entity.

    Catch this to handle any invalid-entity case at once, or catch one of its
    subclasses to react to a specific violation.
    """


class EmptyEntityError(EntityError):
    """Raised when an Entity is built with no detections."""


class MixedLabelError(EntityError):
    """Raised when an Entity's detections do not all share the same label."""
