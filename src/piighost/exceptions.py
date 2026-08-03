"""PIIGhost exception hierarchy.

Every error the library raises derives from PIIGhostError, so a caller can
catch the whole family with a single except PIIGhostError. Specialized
subclasses let a caller react to one specific failure.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from piighost.models import Detection


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


class HasherError(PIIGhostError):
    """Base class for errors raised while constructing a hasher.

    Catch this to handle any invalid-hasher case at once, or catch one of its
    subclasses to react to a specific violation.
    """


class EmptyPepperError(HasherError):
    """Raised when a hasher is built with an empty pepper.

    Hashing without a secret pepper leaves low-entropy PII brute-forceable, so
    the hasher fails closed rather than accept it.
    """


class CipherError(PIIGhostError):
    """Base class for errors raised while constructing a cipher.

    Catch this to handle any invalid-cipher case at once, or catch one of its
    subclasses to react to a specific violation.
    """


class InvalidKeyLengthError(CipherError):
    """Raised when a cipher is built with a key of an unsupported length."""


class GuardError(PIIGhostError):
    """Base class for errors raised by a guard rail.

    Catch this to handle any guard failure at once, or catch one of its
    subclasses to react to a specific violation.
    """


class PIIRemainingError(GuardError):
    """Raised by the pipeline when a guard flags PII left in anonymized text.

    Attributes:
        detections: The residual detections behind the flag, empty when the
            guard is score-based and localizes nothing.
    """

    def __init__(
        self, message: str, detections: "list[Detection] | None" = None
    ) -> None:
        self.detections = detections or []
        super().__init__(message)


class MiddlewareError(PIIGhostError):
    """Base class for errors raised by the anonymization middleware.

    Catch this to handle any middleware failure at once, or catch one of its
    subclasses to react to a specific violation.
    """


class InventedPlaceholderError(MiddlewareError):
    """Raised when deanonymized text still holds a token the pipeline never issued.

    A model can emit a token that matches the placeholder grammar yet was never
    assigned to any entity, whether hallucinated or injected. Under the RAISE
    strategy the middleware refuses it rather than pass it on unrestored.

    Attributes:
        tokens: The invented tokens found, in order of appearance.
    """

    def __init__(self, message: str, tokens: list[str]) -> None:
        self.tokens = tokens
        super().__init__(message)


class MissingThreadIdError(MiddlewareError):
    """Raised when a thread id is required but absent from the LangGraph config.

    With require_thread_id set, the middleware refuses to fall back to the shared
    default thread rather than route unrelated conversations into one bucket.
    """


class UnrecognizableFactoryError(MiddlewareError):
    """Raised when the middleware is built on a factory with no re-findable grammar.

    The middleware needs a delimited placeholder factory, whose tokens it can find
    again to detect ones the model invented. A factory without that grammar, such
    as a mask, cannot support it.
    """
