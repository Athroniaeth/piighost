"""Thread-aware anonymization pipeline: tokens stay consistent across a thread."""

from collections.abc import Mapping

from piighost.components.anonymizer.base import Anonymization, AnyAnonymizer
from piighost.components.detector.base import AnyDetector
from piighost.components.entity_resolver.base import AnyEntityResolver
from piighost.components.expander.base import AnyDetectionExpander
from piighost.components.guard.base import AnyGuardRail
from piighost.components.linker.base import AnyEntityLinker
from piighost.components.overlap_resolver.base import AnyOverlapResolver
from piighost.components.override.base import AnyDetectionOverride
from piighost.components.placeholder.base import AnyPlaceholderFactory
from piighost.conversation_memory.base import (
    AnyConversationMemory,
    Forgotten,
    MessageRole,
)
from piighost.models import Detection, Entity
from piighost.pipeline.base import BaseAnonymizationPipeline, PreservationT


class ThreadAnonymizationPipeline(BaseAnonymizationPipeline[PreservationT]):
    """Anonymize each message of a thread with tokens stable across the thread.

    It extends the base pipeline with a per-thread conversation memory. A value
    keeps one placeholder for the whole thread, so a name seen in an early
    message and again later reads as the same token, because tokens are assigned
    over the union of every message's detections, not one message alone. Each
    message's detections are cached, so resending a message skips detection.

    The token assignment spans the thread, but rendering stays per message: only
    the current message's spans are replaced, since detections from different
    messages share the same offset space and cannot be merged.

    Attributes:
        memory: The per-thread store of each message's detections.
    """

    def __init__(
        self,
        detector: AnyDetector,
        linker: AnyEntityLinker,
        anonymizer: AnyAnonymizer[PreservationT],
        memory: AnyConversationMemory,
        overlap_resolver: AnyOverlapResolver | None = None,
        expander: AnyDetectionExpander | None = None,
        entity_resolver: AnyEntityResolver | None = None,
        guard: AnyGuardRail | None = None,
        observation_redactor: AnyPlaceholderFactory | None = None,
        override: AnyDetectionOverride | None = None,
    ) -> None:
        """Store the stage components and the per-thread conversation memory."""
        super().__init__(
            detector,
            linker,
            anonymizer,
            overlap_resolver,
            expander,
            entity_resolver,
            guard,
            observation_redactor,
            override,
        )
        self.memory = memory

    async def anonymize(
        self,
        text: str,
        thread_id: str,
        role: MessageRole = MessageRole.USER,
    ) -> Anonymization[PreservationT]:
        """Anonymize a message with tokens consistent across its thread.

        The thread_id is required: there is no shared default, so two callers
        cannot fall into one thread and leak each other's PII. The role dates the
        values the message introduces: a value first introduced by the assistant
        is left in clear, since it is not user PII.

        Raises:
            PIIRemainingError: If a guard flags PII left in the output.
        """
        with self._tracer.span("piighost.anonymize") as root:
            root.set_attribute("langfuse.session.id", thread_id)

            with self._tracer.span("piighost.detect") as span:
                detections, cache_hit = await self._detect(text, thread_id, role)
                span.set_attribute("cache_hit", cache_hit)
                span.set_attribute("count", len(detections))
                span.set_output(self._payload_detections(detections))
            root.set_input(self._payload_text(text, detections))

            thread_tokens = await self._thread_tokens(thread_id)
            token_of = {
                detection: token
                for entity, token in thread_tokens.items()
                for detection in entity.detections
            }

            with self._tracer.span("piighost.link") as span:
                message_entities = self.linker.link(detections)
                span.set_output(self._payload_entities(message_entities))

            message_tokens = {
                entity: token_of[entity.detections[0]]
                for entity in message_entities
                if entity.detections[0] in token_of
            }
            preserved = frozenset(
                entity.text.casefold()
                for entity in message_entities
                if entity.detections[0] not in token_of
            )
            anonymizable = list(message_tokens)

            with self._tracer.span("piighost.render") as span:
                rendered = self.anonymizer.render(text, anonymizable, message_tokens)
                span.set_attribute("tokens", len(message_tokens))
                span.set_output(rendered)

            with self._stage_span("piighost.guard", self.guard) as span:
                cleared = await self._cleared_values(text)
                verdict = await self._guard(rendered, preserved | cleared)
                if verdict is not None:
                    labels = sorted({d.label for d in verdict.detections})
                    span.set_output({"flagged": verdict.flagged, "labels": labels})

            root.set_output(rendered)
            return Anonymization(text=rendered, tokens=message_tokens)

    async def anonymize_corrected(
        self,
        text: str,
        thread_id: str,
        detections: list[Detection],
    ) -> Anonymization[PreservationT]:
        """Re-anonymize a user message with a human-corrected detection set.

        The corrected set replaces this message's detections in memory, then the
        message is re-anonymized with tokens consistent across the thread.
        Detection does not run again, since the correction is read from the
        cache. Only a user's own messages are corrected this way, so the
        correction is recorded as a user message. The corrected set is stored as
        given, without overlap resolution or occurrence expansion, since the
        human is authoritative over it. In observation traces the detect span of
        this call reports cache_hit true, since the corrected detections are read
        back from memory rather than re-detected. Server-side overrides are the
        one exception: the corrected set passes through the configured override
        before it is stored, so the server's lists trump the correction.
        """
        corrected = await self._override(text, detections)
        await self.memory.remember(
            thread_id=thread_id,
            message=text,
            detections=corrected,
            role=MessageRole.USER,
        )
        return await self.anonymize(text, thread_id, MessageRole.USER)

    async def deanonymize(self, text: str, thread_id: str) -> str:
        """Return the text with every token from the thread replaced by its value.

        The thread's tokens are rebuilt from its memory, so any text carrying
        them is restored, including a model reply the pipeline never anonymized.
        """
        with self._tracer.span("piighost.deanonymize") as root:
            root.set_input(text)
            thread_tokens = await self._thread_tokens(thread_id)
            restored = self.anonymizer.deanonymize(text, thread_tokens)
            if self.observation_redactor is None:
                root.set_output(restored)
            return restored

    async def forget_thread(self, thread_id: str) -> Forgotten:
        """Erase a thread's memory and report how much was dropped."""
        return await self.memory.forget(thread_id)

    async def _detect(
        self,
        text: str,
        thread_id: str,
        role: MessageRole = MessageRole.USER,
    ) -> tuple[list[Detection], bool]:
        """Return a message's detections and whether they came from the cache."""
        cached = await self.memory.get_detections(thread_id, text)

        if cached is not None:
            return cached, True

        detections = await self.detector.detect(text)
        with self._stage_span("piighost.override", self.override):
            detections = await self._override(text, detections)
        detections = self._resolve_overlaps(detections)
        detections = self._expand(text, detections)
        await self.memory.remember(
            message=text,
            thread_id=thread_id,
            detections=detections,
            role=role,
        )
        return detections, False

    async def _thread_tokens(self, thread_id: str) -> Mapping[Entity, PreservationT]:
        """Assign a token to every anonymizable entity across the thread.

        An entity whose value was first introduced by the assistant is left out,
        so it gets no token and stays in clear.
        """
        union = await self.memory.get_detections(thread_id) or []
        entities = self.linker.link(union)
        thread_entities = self._resolve_entities(entities)
        provenance = await self.memory.get_provenance(thread_id)

        anonymizable = [
            entity
            for entity in thread_entities
            if provenance.get(entity.text.casefold()) is not MessageRole.ASSISTANT
        ]
        return self.anonymizer.create(anonymizable)
