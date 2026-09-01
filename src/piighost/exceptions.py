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


class DetectorError(PIIGhostError):
    """Base class for errors raised while constructing a detector.

    Catch this to handle any invalid-detector case at once, or catch one of its
    subclasses to react to a specific violation.
    """


class LabelMappingError(DetectorError):
    """Raised when a detector's label map has an ambiguous reverse lookup.

    Two external labels that map to the same internal label would make the
    internal-to-external lookup ambiguous, so the detector fails closed rather
    than pick one silently.
    """


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


class AnonymizerError(PIIGhostError):
    """Base class for errors raised by an anonymizer.

    Catch this to handle any anonymizer failure at once, or catch one of its
    subclasses to react to a specific violation.
    """


class OverlappingSpansError(AnonymizerError):
    """Raised when the anonymizer is handed detections whose spans overlap.

    The span-replacement anonymizer rewrites the text in one left-to-right pass
    and assumes disjoint spans, which the overlap-resolver stage guarantees. If
    two spans still overlap it fails closed here rather than splice a clear
    fragment of one detection into the middle of another.
    """


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


class OverrideError(PIIGhostError):
    """Base class for errors raised by a detection override.

    Catch this to handle any override failure at once, or catch one of its
    subclasses to react to a specific violation.
    """


class ConflictingOverrideError(OverrideError):
    """Raised when the whitelist and the blacklist contradict each other.

    Under the RAISE conflict strategy, a span both forced and cleared is a
    configuration error, refused loudly rather than resolved silently.
    """


class ClientError(PIIGhostError):
    """Base class for errors raised by the remote client.

    Catch this to handle any client failure at once, or catch one of its
    subclasses to react to a specific violation.
    """


class RemoteError(ClientError):
    """Raised when the remote piighost-api returns a non-2xx response.

    Attributes:
        status_code: The HTTP status the server returned.
    """

    def __init__(self, message: str, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(message)


class ConfigError(PIIGhostError):
    """Base class for errors raised while loading a configuration.

    Catch this to handle any configuration failure at once, or catch one of its
    subclasses to react to a specific violation.
    """


class ConfigFileError(ConfigError):
    """Raised when a configuration file cannot be read or parsed.

    The file is missing, unreadable, or not valid TOML.
    """


class ConfigValidationError(ConfigError):
    """Raised when a configuration parses but fails schema validation.

    It wraps pydantic's ValidationError in the library's error family, so a
    caller catches ConfigError rather than a pydantic type.
    """


class PIIGhostSecurityWarning(UserWarning):
    """Warned when a persistent backend stores PII in clear without crypto.

    A networked or shared store built without a hasher and cipher keeps PII
    readable to anyone who reads the store. This warns rather than fails, so a
    knowing plaintext setup still works while a forgotten one is loud. It is a
    UserWarning, not a PIIGhostError, since it is a heads-up and not a failure.
    """
