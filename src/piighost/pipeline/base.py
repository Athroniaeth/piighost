"""Anonymization pipeline: chain the stages from detection to anonymized text."""

from collections.abc import Mapping
from typing import Generic, Protocol, runtime_checkable

from typing_extensions import TypeVar

from piighost.components.anonymizer.base import Anonymization, AnyAnonymizer
from piighost.components.detector.base import AnyDetector
from piighost.components.entity_resolver.base import AnyEntityResolver
from piighost.exceptions import PIIRemainingError
from piighost.components.expander.base import AnyDetectionExpander
from piighost.components.guard.base import AnyGuardRail, GuardVerdict
from piighost.components.linker.base import AnyEntityLinker
from piighost.models import Detection, Entity
from piighost.components.overlap_resolver.base import AnyOverlapResolver
from piighost.components.placeholder.tags import PlaceholderPreservation

PreservationT = TypeVar(
    "PreservationT",
    bound=PlaceholderPreservation,
    default=PlaceholderPreservation,
)
PreservationT_co = TypeVar(
    "PreservationT_co",
    bound=PlaceholderPreservation,
    default=PlaceholderPreservation,
    covariant=True,
)


@runtime_checkable
class AnyPipeline(Protocol[PreservationT_co]):
    """A component that anonymizes a text and can restore it.

    Generic on what its tokens preserve, so a consumer such as the middleware can
    require a pipeline whose tokens preserve identity and reject one whose tokens
    do not, at type-check time.
    """

    async def anonymize(self, text: str) -> Anonymization[PreservationT_co]:
        """Return the anonymized text and the token used for each entity.

        Args:
            text: The text to anonymize.

        Returns:
            The anonymized text and the entity-to-token mapping.

        Raises:
            PIIRemainingError: If a guard flags PII left in the output.
        """
        ...

    def deanonymize(self, text: str, tokens: Mapping[Entity, str]) -> str:
        """Return the text with every known token replaced by its entity value.

        Args:
            text: The text whose tokens should be restored.
            tokens: The entity-to-token mapping from an anonymization.

        Returns:
            The text with each known token replaced by its entity's value.
        """
        ...


class BaseAnonymizationPipeline(Generic[PreservationT]):
    """Shared machinery for the anonymization pipelines.

    Holds the stage components and the steps common to every pipeline: the
    optional overlap, expand, and entity-resolve stages, the guard check, and
    deanonymization. The concrete pipelines add their own anonymize, the base one
    over a single text, the thread one over a conversation. Generic on what the
    anonymizer's tokens preserve, so the guarantee flows to a consumer that
    requires identity.

    Attributes:
        detector: The detector run on the text.
        linker: The linker that groups detections into entities.
        anonymizer: The anonymizer that replaces entities with tokens.
        overlap_resolver: The resolver for overlapping detections, or None.
        expander: The expander for missed occurrences, or None.
        entity_resolver: The resolver for entity conflicts, or None.
        guard: The guard re-checking the output, or None.
    """

    def __init__(
        self,
        detector: AnyDetector,
        linker: AnyEntityLinker,
        anonymizer: AnyAnonymizer[PreservationT],
        overlap_resolver: AnyOverlapResolver | None = None,
        expander: AnyDetectionExpander | None = None,
        entity_resolver: AnyEntityResolver | None = None,
        guard: AnyGuardRail | None = None,
    ) -> None:
        """Store the stage components, the optional ones defaulting to disabled."""
        self.detector = detector
        self.linker = linker
        self.anonymizer = anonymizer
        self.overlap_resolver = overlap_resolver
        self.expander = expander
        self.entity_resolver = entity_resolver
        self.guard = guard

    def _resolve_overlaps(self, detections: list[Detection]) -> list[Detection]:
        """Resolve overlapping detections, or pass them through when disabled."""
        if self.overlap_resolver is None:
            return detections
        return self.overlap_resolver.resolve(detections)

    def _expand(self, text: str, detections: list[Detection]) -> list[Detection]:
        """Add missed occurrences, or pass the detections through when disabled."""
        if self.expander is None:
            return detections
        return self.expander.expand(text, detections)

    def _link(self, detections: list[Detection]) -> list[Entity]:
        """Group detections into entities. A subclass may widen this to a thread."""
        return self.linker.link(detections)

    def _resolve_entities(self, entities: list[Entity]) -> list[Entity]:
        """Reconcile entity conflicts, or pass them through when disabled."""
        if self.entity_resolver is None:
            return entities
        return self.entity_resolver.resolve(entities)

    async def _guard(self, text: str) -> None:
        """Raise PIIRemainingError when the guard flags the anonymized text."""
        if self.guard is None:
            return

        verdict = await self.guard.check(text)

        if verdict.flagged:
            raise _pii_remaining(verdict)


class AnonymizationPipeline(BaseAnonymizationPipeline[PreservationT]):
    """Anonymize a single text through the pipeline stages.

    Detect the PII, resolve overlaps, expand missed occurrences, link into
    entities, resolve entity conflicts, replace with tokens, and re-check with a
    guard, in that order.
    """

    async def anonymize(self, text: str) -> Anonymization[PreservationT]:
        """Return the anonymized text and token mapping for the given text.

        Raises:
            PIIRemainingError: If a guard flags PII left in the output.
        """
        detections = await self.detector.detect(text)
        detections = self._resolve_overlaps(detections)
        detections = self._expand(text, detections)
        entities = self._link(detections)
        entities = self._resolve_entities(entities)

        result = self.anonymizer.anonymize(text, entities)
        await self._guard(result.text)
        return result

    def deanonymize(self, text: str, tokens: Mapping[Entity, str]) -> str:
        """Return the text with every known token replaced by its entity value."""
        return self.anonymizer.deanonymize(text, tokens)


def _pii_remaining(verdict: GuardVerdict) -> PIIRemainingError:
    """Build the error for a flagged verdict, naming its labels or its score."""
    detections = list(verdict.detections)

    if detections:
        labels = sorted({detection.label for detection in detections})
        return PIIRemainingError(
            f"Anonymized text still contains PII: {labels}", detections
        )

    return PIIRemainingError(f"A guard flagged residual PII (score {verdict.score})")
