"""Thread-aware anonymization pipeline: tokens stay consistent across a thread."""

from piighost.anonymizer.base import Anonymization, AnyAnonymizer
from piighost.conversation_memory.base import AnyConversationMemory, Forgotten
from piighost.detector.base import AnyDetector
from piighost.entity_resolver.base import AnyEntityResolver
from piighost.expander.base import AnyDetectionExpander
from piighost.guard.base import AnyGuardRail
from piighost.linker.base import AnyEntityLinker
from piighost.models import Detection
from piighost.overlap_resolver.base import AnyOverlapResolver
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
        )
        self.memory = memory

    async def anonymize(
        self,
        text: str,
        thread_id: str,
    ) -> Anonymization[PreservationT]:
        """Anonymize a message with tokens consistent across its thread.

        The thread_id is required: there is no shared default, so two callers
        cannot fall into one thread and leak each other's PII.

        Raises:
            PIIRemainingError: If a guard flags PII left in the output.
        """
        detections = await self._detect(text, thread_id)
        union = await self.memory.get_detections(thread_id) or []
        thread_entities = self._resolve_entities(self.linker.link(union))
        thread_tokens = self.anonymizer.create(thread_entities)
        token_of = {
            detection: token
            for entity, token in thread_tokens.items()
            for detection in entity.detections
        }

        message_entities = self.linker.link(detections)
        message_tokens = {
            entity: token_of[entity.detections[0]] for entity in message_entities
        }
        rendered = self.anonymizer.render(text, message_entities, message_tokens)

        await self._guard(rendered)
        return Anonymization(text=rendered, tokens=message_tokens,)

    async def forget_thread(self, thread_id: str) -> Forgotten:
        """Erase a thread's memory and report how much was dropped."""
        return await self.memory.forget(thread_id)

    async def _detect(self, text: str, thread_id: str) -> list[Detection]:
        """Return a message's detections, from cache or a fresh cleaned detection."""
        cached = await self.memory.get_detections(thread_id, text)

        if cached is not None:
            return cached

        detections = await self.detector.detect(text)
        detections = self._resolve_overlaps(detections)
        detections = self._expand(text, detections)
        await self.memory.remember(
            message=text,
            thread_id=thread_id,
            detections=detections,
        )
        return detections
