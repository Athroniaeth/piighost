"""Anonymization pipeline: chain the stages from detection to anonymized text."""

from collections.abc import Mapping
from contextlib import AbstractContextManager, nullcontext
from dataclasses import replace
from typing import Any, Generic, Protocol, cast, runtime_checkable

from typing_extensions import TypeVar

from piighost.components.anonymizer import Anonymizer
from piighost.components.anonymizer.base import Anonymization, AnyAnonymizer
from piighost.components.detector.base import AnyDetector
from piighost.components.entity_resolver.base import AnyEntityResolver
from piighost.components.expander.base import AnyDetectionExpander
from piighost.components.guard.base import AnyGuardRail, GuardVerdict
from piighost.components.linker import ExactEntityLinker
from piighost.components.linker.base import AnyEntityLinker
from piighost.components.overlap_resolver.base import AnyOverlapResolver
from piighost.components.override.base import AnyDetectionOverride
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.components.placeholder.base import (
    AnyPlaceholderFactory,
    BaseDelimitedPlaceholderFactory,
)
from piighost.components.placeholder.tags import PlaceholderPreservation
from piighost.conversation_memory.base import Forgotten, MessageRole
from piighost.exceptions import PIIRemainingError
from piighost.models import Detection, Entity
from piighost.observation import AnyObservationSpan, NoOpSpan, get_tracer

PreservationT = TypeVar(
    "PreservationT",
    bound=PlaceholderPreservation,
    default=PlaceholderPreservation,
)
"""What the concrete pipeline's tokens preserve, invariant on the implementations.

Invariant, since a pipeline both consumes its anonymizer's tag and hands the same
tokens back out, so it cannot vary in either direction.
"""

PreservationT_co = TypeVar(
    "PreservationT_co",
    bound=PlaceholderPreservation,
    default=PlaceholderPreservation,
    covariant=True,
)
"""What a pipeline's tokens preserve, on the AnyPipeline and AnyThreadPipeline ports.

Covariant, so a pipeline whose tokens preserve identity satisfies a consumer such
as the middleware that requires only identity or less.
"""


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


@runtime_checkable
class AnyThreadPipeline(Protocol[PreservationT_co]):
    """A thread-scoped pipeline, local or remote, anonymizing a conversation.

    It anonymizes each message of a thread with tokens stable across the thread,
    re-anonymizes a human-corrected message, deanonymizes any text carrying the
    thread's tokens, and forgets a thread wholesale. It also exposes the grammar
    of the tokens it emits, so a consumer such as the middleware can find them
    again without reaching into a local anonymizer, which a remote pipeline does
    not have. Being runtime_checkable, an isinstance check confirms only that
    these members are present, not their signatures.
    """

    async def anonymize(
        self, text: str, thread_id: str, role: MessageRole = MessageRole.USER
    ) -> Anonymization[PreservationT_co]:
        """Return the anonymized message and the token used for each entity."""
        ...

    async def anonymize_corrected(
        self, text: str, thread_id: str, detections: list[Detection]
    ) -> Anonymization[PreservationT_co]:
        """Re-anonymize a user message with a human-corrected detection set."""
        ...

    async def deanonymize(self, text: str, thread_id: str) -> str:
        """Return the text with every token from the thread replaced by its value."""
        ...

    async def forget_thread(self, thread_id: str) -> Forgotten:
        """Erase a thread's memory and report how much was dropped."""
        ...

    @property
    def recognizer(self) -> BaseDelimitedPlaceholderFactory | None:
        """The grammar of the tokens this pipeline emits, or None if none."""
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
        linker: The linker that groups detections into entities. Defaults to an
            ExactEntityLinker.
        anonymizer: The anonymizer that replaces entities with tokens. Defaults
            to an Anonymizer with a LabelCounterPlaceholderFactory.
        overlap_resolver: The resolver for overlapping detections, or None.
        expander: The expander for missed occurrences, or None.
        entity_resolver: The resolver for entity conflicts, or None.
        guard: The guard re-checking the output, or None.
        override: The server override imposed on every detection set, or None.
    """

    def __init__(
        self,
        detector: AnyDetector,
        linker: AnyEntityLinker | None = None,
        anonymizer: AnyAnonymizer[PreservationT] | None = None,
        overlap_resolver: AnyOverlapResolver | None = None,
        expander: AnyDetectionExpander | None = None,
        entity_resolver: AnyEntityResolver | None = None,
        guard: AnyGuardRail | None = None,
        observation_redactor: AnyPlaceholderFactory | None = None,
        override: AnyDetectionOverride | None = None,
    ) -> None:
        """Store the stage components, the optional ones defaulting to disabled.

        Only the detector is required. Omitting linker builds an ExactEntityLinker,
        and omitting anonymizer builds an Anonymizer with a
        LabelCounterPlaceholderFactory, so the smallest pipeline is
        AnonymizationPipeline(detector).

        observation_redactor controls the observation payloads: None, the
        default, traces the clear text and detection values, so traces double as
        annotation datasets; a placeholder factory replaces those values with its
        tokens, making traces safe for a PII-untrusted backend but unusable as
        datasets. override imposes the server's whitelist and blacklist on every
        detection set, trumping the detector and any corrected set.
        """
        self.detector = detector
        self.linker = linker or ExactEntityLinker()
        # The default anonymizer's tag is fixed, but the caller left PreservationT
        # unbound, so cast to widen it. The tokens it preserves satisfy any consumer
        # of the widened default.
        default_factory = LabelCounterPlaceholderFactory()
        default_anonymizer = cast(
            "AnyAnonymizer[PreservationT]", Anonymizer(default_factory)
        )
        self.anonymizer = anonymizer or default_anonymizer
        self.overlap_resolver = overlap_resolver
        self.expander = expander
        self.entity_resolver = entity_resolver
        self.guard = guard
        self.observation_redactor = observation_redactor
        self.override = override
        self._tracer = get_tracer()

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

    async def _override(
        self, text: str, detections: list[Detection]
    ) -> list[Detection]:
        """Impose the override, or pass detections through when disabled."""
        if self.override is None:
            return detections
        return await self.override.apply(text, detections)

    async def _cleared_values(self, text: str) -> frozenset[str]:
        """The values the blacklist clears here, exempted from the guard.

        A blacklisted value is deliberately left in clear, so a detector-based
        guard would re-find it and refuse the output. Empty when no override or
        no guard is configured, since the exemption only serves the guard.
        """
        if self.override is None or self.guard is None:
            return frozenset()
        return await self.override.cleared_values(text)

    async def _forces_value(self, value: str) -> bool:
        """Whether the override's whitelist forces this value to a token."""
        if self.override is None:
            return False
        return await self.override.forces_value(value)

    def _stage_span(
        self, name: str, component: object | None
    ) -> AbstractContextManager[AnyObservationSpan]:
        """Open a stage span when the component is configured, else a no-op."""
        if component is None:
            return nullcontext(NoOpSpan())
        return self._tracer.span(name)

    def _payload_detections(self, detections: list[Detection]) -> list[dict[str, Any]]:
        """Serialize detections for a span payload, tokened when redacting."""
        if self.observation_redactor is None:
            return [detection.to_dict() for detection in detections]
        tokens = self._redaction_tokens(detections)
        return [
            {**detection.to_dict(), "text": tokens[detection]}
            for detection in detections
        ]

    def _payload_entities(self, entities: list[Entity]) -> list[dict[str, Any]]:
        """Serialize entities for a span payload, tokened when redacting."""
        if self.observation_redactor is None:
            values = {entity: entity.text for entity in entities}
        else:
            tokens = self.observation_redactor.create(entities)
            values = {entity: str(tokens[entity]) for entity in entities}
        return [
            {
                "text": values[entity],
                "label": entity.label,
                "occurrences": len(entity.detections),
            }
            for entity in entities
        ]

    def _payload_text(self, text: str, detections: list[Detection]) -> str:
        """Return a text payload, its detection spans tokened when redacting.

        Overlapping spans are merged before splicing, so the union of every
        detection span is removed and no clear fragment of one detection can
        survive a splice made for another. A merged range takes the token of its
        first detection.
        """
        if self.observation_redactor is None:
            return text
        tokens = self._redaction_tokens(detections)
        merged: list[tuple[int, int, str]] = []
        for detection in sorted(detections, key=lambda detection: detection.span):
            span = detection.span
            if merged and span.start < merged[-1][1]:
                start, end, token = merged[-1]
                merged[-1] = (start, max(end, span.end), token)
            else:
                merged.append((span.start, span.end, tokens[detection]))
        redacted = text
        for start, end, token in reversed(merged):
            redacted = redacted[:start] + token + redacted[end:]
        return redacted

    def _redaction_tokens(self, detections: list[Detection]) -> dict[Detection, str]:
        """Token every detection with the redactor, grouped so values share one."""
        redactor = self.observation_redactor
        if redactor is None:
            return {}
        entities = self.linker.link(detections)
        tokens = redactor.create(entities)
        return {
            detection: str(tokens[entity])
            for entity in entities
            for detection in entity.detections
        }

    async def _guard(
        self, text: str, expected: frozenset[str] = frozenset()
    ) -> GuardVerdict | None:
        """Check the guard and raise on unexpected PII, returning the verdict.

        Values in expected are ones the pipeline chose to leave in clear, such as
        an entity the assistant introduced. A detector-based guard would re-find
        them, so they are dropped from the verdict before deciding. A score-based
        guard localizes nothing, so it cannot be filtered this way. Returns None
        when no guard is configured, else the verdict that passed.
        """
        if self.guard is None:
            return None

        verdict = await self.guard.check(text)

        if verdict.detections:
            residual = tuple(
                detection
                for detection in verdict.detections
                if detection.text.casefold() not in expected
            )
            if not residual:
                return replace(verdict, flagged=False, detections=())
            verdict = replace(verdict, detections=residual)

        if verdict.flagged:
            raise _pii_remaining(verdict)
        return verdict


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
        with self._tracer.span("piighost.anonymize") as root:
            with self._tracer.span("piighost.detect") as span:
                detections = await self.detector.detect(text)
                span.set_attribute("count", len(detections))
                span.set_output(self._payload_detections(detections))

            with self._stage_span("piighost.override", self.override):
                detections = await self._override(text, detections)
            root.set_input(self._payload_text(text, detections))

            with self._stage_span("piighost.overlap", self.overlap_resolver):
                detections = self._resolve_overlaps(detections)
            with self._stage_span("piighost.expand", self.expander):
                detections = self._expand(text, detections)

            with self._tracer.span("piighost.link") as span:
                entities = self._link(detections)
                span.set_output(self._payload_entities(entities))

            with self._stage_span("piighost.entity_resolve", self.entity_resolver):
                entities = self._resolve_entities(entities)

            with self._tracer.span("piighost.render") as span:
                result = self.anonymizer.anonymize(text, entities)
                span.set_attribute("tokens", len(result.tokens))
                span.set_output(result.text)

            with self._stage_span("piighost.guard", self.guard) as span:
                cleared = await self._cleared_values(text)
                verdict = await self._guard(result.text, cleared)
                if verdict is not None:
                    labels = sorted({d.label for d in verdict.detections})
                    span.set_output({"flagged": verdict.flagged, "labels": labels})

            root.set_output(result.text)
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
