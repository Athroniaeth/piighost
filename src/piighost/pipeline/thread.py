"""Thread-aware anonymization pipeline: tokens stay consistent across a thread."""

import time
from collections import OrderedDict
from collections.abc import Callable, Mapping

from piighost.components.anonymizer.base import Anonymization, AnyAnonymizer
from piighost.components.detector.base import AnyDetector
from piighost.components.entity_resolver.base import AnyEntityResolver
from piighost.components.expander.base import AnyDetectionExpander
from piighost.components.guard.base import AnyGuardRail
from piighost.components.linker.base import AnyEntityLinker
from piighost.components.overlap_resolver.base import AnyOverlapResolver
from piighost.components.override.base import AnyDetectionOverride
from piighost.components.placeholder.base import (
    AnyPlaceholderFactory,
    BaseDelimitedPlaceholderFactory,
)
from piighost.conversation_memory.base import (
    AnyConversationMemory,
    Forgotten,
    MessageRole,
)
from piighost.conversation_memory.memory import InMemoryConversationMemory
from piighost.models import Detection, Entity
from piighost.pipeline.base import BaseAnonymizationPipeline, PreservationT

_TOKEN_MEMO_MAX = 256
"""How many thread-token maps to memoize before evicting the least recently used."""

_MemoKey = tuple[object, ...]
"""What a memoized thread-token map is keyed on: the thread and the state it derives from."""


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
        linker: AnyEntityLinker | None = None,
        anonymizer: AnyAnonymizer[PreservationT] | None = None,
        memory: AnyConversationMemory | None = None,
        overlap_resolver: AnyOverlapResolver | None = None,
        expander: AnyDetectionExpander | None = None,
        entity_resolver: AnyEntityResolver | None = None,
        guard: AnyGuardRail | None = None,
        observation_redactor: AnyPlaceholderFactory | None = None,
        override: AnyDetectionOverride | None = None,
        trace_clear_text: bool = False,
        token_memo_ttl: float | None = None,
        time_source: Callable[[], float] = time.monotonic,
    ) -> None:
        """Store the stage components and the per-thread conversation memory.

        Only the detector is required. As in the base pipeline, omitting linker
        or anonymizer builds their defaults, and omitting memory builds an
        InMemoryConversationMemory, so the smallest thread pipeline is
        ThreadAnonymizationPipeline(detector).

        token_memo_ttl bounds how long a memoized thread-token map is kept. That
        memo holds the thread's values in clear, and forget_thread only reaches
        the memo of the process it runs in, so on a multi-worker deployment the
        other workers keep theirs until eviction. A ttl bounds that window on
        every worker without any cross-worker coordination. Left unset, an entry
        lives until the size bound evicts it. time_source is the clock the ttl
        reads, injectable for tests.
        """
        memory = memory or InMemoryConversationMemory()
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
            trace_clear_text,
        )
        self.memory = memory
        # Memoize the thread-token map by the content it derives from, so
        # rewriting every message of a long history in one turn, or resolving a
        # stream token by token, does not relink and re-resolve the whole thread
        # each time. Keyed on the union and provenance actually read, so a change
        # from any writer yields a new key; bounded, evicting least recently used.
        self._token_memo: OrderedDict[_MemoKey, Mapping[Entity, PreservationT]] = (
            OrderedDict()
        )
        self._token_memo_expiry: dict[_MemoKey, float] = {}
        self._token_memo_ttl = token_memo_ttl
        self._now = time_source
        # Bumped by every erasure, read across the awaits of a derivation, so a
        # derivation that straddles an erasure declines to memoize its result.
        self._forget_epoch = 0

    @property
    def recognizer(self) -> BaseDelimitedPlaceholderFactory | None:
        """The grammar of the tokens this pipeline emits, or None if none.

        A delimited factory is its own recognizer, since its tokens carry a
        grammar that can be found again; a factory without one, such as a mask,
        has no recognizer.
        """
        factory = self.anonymizer.factory
        if isinstance(factory, BaseDelimitedPlaceholderFactory):
            return factory
        return None

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

    async def thread_token_map(self, thread_id: str) -> dict[str, str]:
        """Return the thread's placeholder-to-value map, derived from the cache.

        It is the same cache-derived mapping deanonymize replaces against, exposed
        as token to value so a caller can resolve a whole stream once rather than
        deanonymizing token by token. A token the thread never issued is absent
        from the map, matching deanonymize leaving an unknown token as it stood.
        """
        thread_tokens = await self._thread_tokens(thread_id)
        return {f"{token}": entity.text for entity, token in thread_tokens.items()}

    async def forget_thread(self, thread_id: str) -> Forgotten:
        """Erase a thread's memory and its memoized tokens, reporting what dropped.

        The token memo holds the thread's values in clear, so it is purged here
        too: erasing the store alone would leave a forgotten thread's PII live in
        this process. A derivation already in flight is covered as well, since
        the erasure bumps the epoch it reads, so it declines to memoize a result
        it built from the state this call erased.

        The word-boundary pattern cache is process-wide rather than per thread,
        so it is left alone; clear it with clear_boundary_cache when an erasure
        request covers the whole process.
        """
        forgotten = await self.memory.forget(thread_id)
        self._forget_epoch += 1
        self._forget_token_memo(thread_id)
        return forgotten

    def _forget_token_memo(self, thread_id: str) -> None:
        """Drop every memoized token map derived from this thread."""
        stale = [key for key in self._token_memo if key[0] == thread_id]
        for key in stale:
            self._drop_memo(key)

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
        so it gets no token and stays in clear, unless the override's whitelist
        forces it under the FORCE strategy.

        The result is memoized by the union and provenance it derives from, so
        repeated calls within a turn skip relinking and re-resolving the whole
        thread. The reads still happen, so a change from any writer produces a new
        key and a fresh computation.

        The result is still returned when an erasure lands mid-derivation, since
        the caller's own request was already in flight, but it is not memoized:
        caching it would put the erased thread's values back in the memo.
        """
        epoch = self._forget_epoch
        self._expire_memo()
        union = await self.memory.get_detections(thread_id) or []
        provenance = await self.memory.get_provenance(thread_id)

        key = (
            thread_id,
            tuple(union),
            tuple(sorted(provenance.items(), key=lambda item: item[0])),
        )
        cached = self._token_memo.get(key)
        if cached is not None:
            self._token_memo.move_to_end(key)
            return cached

        entities = self.linker.link(union)
        thread_entities = self._resolve_entities(entities)

        anonymizable = []
        for entity in thread_entities:
            introduced_by_assistant = (
                provenance.get(entity.text.casefold()) is MessageRole.ASSISTANT
            )
            if not introduced_by_assistant or await self._forces_value(entity.text):
                anonymizable.append(entity)

        tokens = self.anonymizer.create(anonymizable)
        if epoch != self._forget_epoch:
            return tokens
        self._token_memo[key] = tokens
        self._token_memo.move_to_end(key)
        if self._token_memo_ttl is not None:
            self._token_memo_expiry[key] = self._now() + self._token_memo_ttl
        self._evict_memo()
        return tokens

    def _expire_memo(self) -> None:
        """Drop the memoized token maps whose ttl has passed.

        Swept from the front rather than checked lazily per key: a thread that
        gains a message derives a new key, so the entry of an older generation is
        never looked up again and a lazy check would never reach it, which is
        exactly the entry a ttl exists to bound. Every entry shares one ttl and
        the deadlines sit in write order, so the sweep stops at the first live
        one and costs nothing when none has expired.
        """
        if self._token_memo_ttl is None:
            return

        now = self._now()
        while self._token_memo_expiry:
            key = next(iter(self._token_memo_expiry))
            if now < self._token_memo_expiry[key]:
                break
            self._drop_memo(key)

    def _drop_memo(self, key: _MemoKey) -> None:
        """Remove one memoized token map and its expiry deadline."""
        self._token_memo.pop(key, None)
        self._token_memo_expiry.pop(key, None)

    def _evict_memo(self) -> None:
        """Evict least recently used token maps while over the size bound."""
        while len(self._token_memo) > _TOKEN_MEMO_MAX:
            oldest, _ = self._token_memo.popitem(last=False)
            self._token_memo_expiry.pop(oldest, None)
