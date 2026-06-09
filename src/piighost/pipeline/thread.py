"""Conversation-aware anonymization pipeline.

Wraps :class:`AnonymizationPipeline` with a :class:`ConversationMemory`
to accumulate entities across messages.  Provides ``deanonymize_with_ent``
and ``anonymize_with_ent`` for single-pass regex replacement on any text
containing known tokens or original values.

Conversation-scoped memory for accumulating entities across messages.

Stores all :class:`Entity` objects seen during a conversation, indexed
by message hash and deduplicated by ``(text.lower(), label)``.  The
``all_entities`` property returns a flat, append-only list used by the
pipeline to recreate consistent placeholder tokens across messages.
"""

import asyncio
import logging
import re
import warnings
from collections import OrderedDict, defaultdict
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any, Mapping, Protocol

from typing_extensions import TypeVar

from aiocache import BaseCache, SimpleMemoryCache

from piighost.anonymizer import AnyAnonymizer
from piighost.detector import AnyDetector
from piighost.exceptions import PIIGhostConfigWarning
from piighost.guard import AnyGuardRail
from piighost.linker.entity import AnyEntityLinker
from piighost.models import Detection, Entity
from piighost.observation.base import AbstractObservationService, AbstractSpan
from piighost.pipeline.base import (
    CACHE_KEY_ANON_RESULT,
    CACHE_KEY_ANONYMIZATION,
    CACHE_KEY_DETECTION,
    DEFAULT_CACHE_TTL,
    AnonymizationPipeline,
)
from piighost.placeholder import AnyPlaceholderFactory
from piighost.placeholder_tags import (
    PlaceholderPreservation,
    PreservesIdentity,
    get_preservation_tag,
)
from piighost.resolver.entity import AnyEntityConflictResolver
from piighost.resolver.span import AnySpanConflictResolver
from piighost.utils import boundary_wrap, hash_sha256

logger = logging.getLogger(__name__)

PreservationT = TypeVar(
    "PreservationT",
    bound=PlaceholderPreservation,
    default=PlaceholderPreservation,
)

_current_thread_id: ContextVar[str] = ContextVar(
    "piighost_current_thread_id", default="default"
)
"""Active thread id for the running coroutine.

Used by :class:`ThreadAnonymizationPipeline` to propagate the ``thread_id``
argument down to the cache-key helpers without mutating instance state,
which would be unsafe when several coroutines share one pipeline.
"""

_multi_instance_warning_emitted: bool = False
"""Process-wide flag so the unshared-cache warning fires at most once.

Module-level rather than class-level: the semantics are "has any pipeline
in this process already warned?", which is module state, not class state.
"""


def _replace_longest_first(
    text: str,
    pairs: list[tuple[str, str]],
    *,
    word_boundary: bool = False,
) -> str:
    """Replace every *source* with its *target* in one regex pass.

    Sources are emitted longest-first in the alternation so that a match
    on a longer source wins over any shorter prefix.  Duplicate sources
    are collapsed: the first mapping wins.  Returns *text* unchanged
    when ``pairs`` is empty.

    When ``word_boundary`` is true, each source only matches at word
    boundaries.  Use it when sources are raw PII surface forms (so
    "Ali" does not match inside "Alibaba").  Leave it false when
    sources are placeholder tokens: their ``<<...>>`` delimiters
    already isolate them, and an LLM may glue a token to a word.
    """
    mapping: dict[str, str] = {}
    for source, target in pairs:
        if source and source not in mapping:
            mapping[source] = target

    if not mapping:
        return text

    sources = sorted(mapping, key=len, reverse=True)
    if word_boundary:
        alternation = "|".join(boundary_wrap(s) for s in sources)
    else:
        alternation = "|".join(re.escape(s) for s in sources)
    pattern = re.compile(alternation)
    return pattern.sub(lambda m: mapping[m.group(0)], text)


class AnyConversationMemory(Protocol):
    """Protocol for conversation memory implementations."""

    entities_by_hash: dict[str, list[Entity]]

    @property
    def all_entities(self) -> list[Entity]: ...

    def record(self, text_hash: str, entities: list[Entity]) -> bool: ...

    def to_dict(self) -> dict[str, Any]: ...

    def merge_snapshot(self, data: dict[str, Any]) -> None: ...


class ConversationMemory:
    """In-memory conversation memory that accumulates entities across messages.

    Entities are stored per message hash and deduplicated by canonical
    identity ``(text.lower(), label)``.  The ``all_entities`` property
    flattens all stored entities in insertion order, skipping duplicates.

    An internal canonical index makes ``record()`` lookups O(1) instead
    of scanning every previously-seen entity.  The index points at the
    current slot of each canonical entity inside ``entities_by_hash``
    so that merging a new surface-form variant stays O(1) too.

    Example:
        >>> from piighost.models import Detection, Entity, Span
        >>> memory = ConversationMemory()
        >>> e = Entity(detections=(Detection("Patrick", "PERSON", Span(0, 7), 0.9),))
        >>> memory.record("abc123", [e])
        True
        >>> memory.all_entities[0].canonical
        'patrick'
    """

    def __init__(
        self,
        entities_by_hash: dict[str, list[Entity]] | None = None,
    ) -> None:
        self.entities_by_hash: dict[str, list[Entity]] = (
            entities_by_hash if entities_by_hash is not None else {}
        )
        self._canonical_index: dict[tuple[str, str], tuple[str, int]] = {}

    def record(self, text_hash: str, entities: list[Entity]) -> bool:
        """Record entities for a message, deduplicating against known ones.

        Known entities are not duplicated but their new text variants
        (e.g. ``"france"`` when ``"France"`` already exists) are merged
        into the existing entity so that ``anonymize_with_ent`` can
        replace all surface forms.

        Args:
            text_hash: SHA-256 hash of the original text.
            entities: Entities detected in that message.

        Returns:
            ``True`` when this call changed the memory (a new entity was
            appended or a new surface-form variant was merged), ``False``
            when everything recorded was already known.  Callers use this
            to skip persisting an unchanged snapshot.
        """
        bucket = self.entities_by_hash.setdefault(text_hash, [])

        changed = False
        for entity in entities:
            key = self._key(entity)
            slot = self._canonical_index.get(key)
            if slot is None:
                bucket.append(entity)
                self._canonical_index[key] = (text_hash, len(bucket) - 1)
                changed = True
            elif self._merge_variant(slot, entity):
                changed = True
        return changed

    @property
    def all_entities(self) -> list[Entity]:
        """Flat deduplicated list of all entities, in insertion order."""
        return [
            self.entities_by_hash[text_hash][index]
            for text_hash, index in self._canonical_index.values()
        ]

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly snapshot preserving insertion (first-seen) order.

        Buckets without entities are skipped: replaying an empty bucket
        is a no-op, and keeping them would grow the snapshot with every
        PII-free message.
        """
        return {
            "entities_by_hash": {
                text_hash: [e.to_dict() for e in bucket]
                for text_hash, bucket in self.entities_by_hash.items()
                if bucket
            }
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConversationMemory":
        """Rebuild a memory by replaying the snapshot through ``record``."""
        memory = cls()
        memory.merge_snapshot(data)
        return memory

    def merge_snapshot(self, data: dict[str, Any]) -> None:
        """Replay *data* into this memory; idempotent (record dedups)."""
        for text_hash, bucket in data.get("entities_by_hash", {}).items():
            self.record(text_hash, [Entity.from_dict(e) for e in bucket])

    @staticmethod
    def _key(entity: Entity) -> tuple[str, str]:
        """Canonical identity used for deduplication."""
        return entity.canonical_key

    def _merge_variant(self, slot: tuple[str, int], entity: Entity) -> bool:
        """Merge a new surface-form variant into the entity at *slot*.

        Detections whose exact ``text`` already belongs to the stored
        entity are skipped; anything new is appended so that
        ``anonymize_with_ent`` can replace every observed spelling.

        Returns ``True`` when a new variant was merged, ``False`` when
        every detection was already known.
        """
        text_hash, index = slot
        bucket = self.entities_by_hash[text_hash]
        existing = bucket[index]
        existing_texts = {d.text for d in existing.detections}
        new_dets = tuple(d for d in entity.detections if d.text not in existing_texts)
        if new_dets:
            bucket[index] = Entity(detections=existing.detections + new_dets)
            return True
        return False


class ThreadAnonymizationPipeline(AnonymizationPipeline[PreservationT]):
    """Adds conversation memory on top of ``AnonymizationPipeline``.

    Delegates detection, resolution, and span-based anonymization to the
    base pipeline.  After each ``anonymize()`` call, entities are recorded
    in memory so that ``deanonymize_with_ent`` / ``anonymize_with_ent``
    can operate on *any* text via a single regex-alternation pass.

    Memory and cache are isolated per ``thread_id`` passed to each
    method.  Cache keys are prefixed with the thread id so that a
    shared Redis backend keeps conversations separate.  The default
    thread id is ``"default"``.

    The stage hooks (``_link_stage``, ``_record_entities``,
    ``_render_stage``) are only valid under a ``_current_thread_id`` set by
    ``anonymize``; calling base methods like ``detect_entities()`` directly
    on a thread pipeline routes caching to the ``"default"`` thread.

    Args:
        detector: The entity detector to use.
        span_resolver: The span conflict resolver to use.
        entity_linker: The entity linker to use.
        entity_resolver: The entity conflict resolver to use.
        anonymizer: The anonymizer to use for span-based replacement.
        cache: Optional aiocache backend.  Defaults to a fresh
            ``SimpleMemoryCache``.
        cache_ttl: Time-to-live in seconds for every cache entry the
            pipeline writes.  Defaults to one hour; pass ``None`` to keep
            entries until the backend evicts them.
        max_threads: Maximum number of conversation memories kept in
            RAM.  When a new thread is created past the cap, the least
            recently used memory is evicted.  ``None`` (default)
            disables the cap; use it with caution on long-running
            servers that juggle many conversations.
        memory_factory: Callable returning a fresh
            ``AnyConversationMemory`` for each new thread.  Defaults to
            ``ConversationMemory``.  Inject a custom implementation to
            change deduplication or storage semantics; it must support
            ``to_dict`` / ``merge_snapshot`` so memory snapshots can
            round-trip through the cache backend.
    """

    def __init__(
        self,
        detector: AnyDetector,
        anonymizer: AnyAnonymizer[PreservationT],
        entity_linker: AnyEntityLinker | None = None,
        entity_resolver: AnyEntityConflictResolver | None = None,
        span_resolver: AnySpanConflictResolver | None = None,
        guard_rail: AnyGuardRail | None = None,
        cache: BaseCache | None = None,
        cache_ttl: int | None = DEFAULT_CACHE_TTL,
        max_threads: int | None = None,
        memory_factory: Callable[[], AnyConversationMemory] | None = None,
        observation: AbstractObservationService | None = None,
        observation_ph_factory: AnyPlaceholderFactory | None = None,
    ) -> None:
        if max_threads is not None and max_threads <= 0:
            raise ValueError(f"max_threads must be positive or None, got {max_threads}")
        self._reject_non_identity_factory(anonymizer.ph_factory)

        super().__init__(
            detector,
            span_resolver=span_resolver,
            entity_linker=entity_linker,
            entity_resolver=entity_resolver,
            anonymizer=anonymizer,
            guard_rail=guard_rail,
            cache=cache,
            cache_ttl=cache_ttl,
            observation=observation,
            observation_ph_factory=observation_ph_factory,
        )

        self._memory_factory: Callable[[], AnyConversationMemory] = (
            memory_factory or ConversationMemory
        )
        self._memories: OrderedDict[str, AnyConversationMemory] = OrderedDict()
        self._max_threads = max_threads
        self._index_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        # Index TTL: far longer than the data TTL so forget_thread still
        # finds expired-entry keys, yet bounded so deployments that never
        # call forget_thread do not grow indexes forever.  With
        # cache_ttl=None data never expires, so the index keeps ttl=None.
        self._index_ttl: int | None = (
            self._cache_ttl * 24 if self._cache_ttl is not None else None
        )
        self._maybe_warn_unshared_cache()

    def _maybe_warn_unshared_cache(self) -> None:
        """Warn once per process when the active cache is process-local.

        Multi-instance deployments behind a load balancer need a shared
        backend, otherwise the same ``thread_id`` routed to two workers
        sees inconsistent placeholders mid-conversation.  The warning
        focuses on correctness (cross-worker placeholder consistency),
        not performance.
        """
        global _multi_instance_warning_emitted
        if _multi_instance_warning_emitted:
            return
        if not isinstance(self._cache, SimpleMemoryCache):
            return
        _multi_instance_warning_emitted = True
        warnings.warn(
            "ThreadAnonymizationPipeline is using a process-local cache "
            "(SimpleMemoryCache). In a multi-instance deployment behind a "
            "load balancer, the placeholder mapping is not shared across "
            "workers: the same thread_id routed to two workers will see "
            "Patrick assigned to <<PERSON:1>> on one worker and "
            "<<PERSON:2>> on the next, breaking placeholder consistency "
            "mid-conversation. For multi-worker deployments, configure a "
            "shared cache backend (e.g. RedisCache). See the "
            "'Multi-instance deployment' page in the documentation. "
            "Silence this warning with "
            "warnings.filterwarnings('ignore', category=PIIGhostConfigWarning).",
            PIIGhostConfigWarning,
            stacklevel=3,
        )

    @staticmethod
    def _reject_non_identity_factory(factory: object) -> None:
        """Raise if the factory does not advertise ``PreservesIdentity``.

        Mirrors the static-typing constraint: the middleware and
        conversation-memory logic both assume each entity maps to a
        unique, reversible token, so factories tagged with a weaker
        preservation level are rejected upfront.
        """
        tag = get_preservation_tag(factory)
        if tag is None:
            # Untyped factory: accept but trust the caller. Preserves
            # backwards-compat with user-defined factories that haven't
            # adopted the phantom-tag system yet.
            return
        if not issubclass(tag, PreservesIdentity):
            raise ValueError(
                f"{type(factory).__name__} is tagged "
                f"'{tag.__name__}' and cannot be used with "
                f"ThreadAnonymizationPipeline, which requires a factory "
                f"tagged 'PreservesIdentity' so tokens can be "
                f"deanonymised per-entity. "
                f"Use LabelCounterPlaceholderFactory or LabelHashPlaceholderFactory instead."
            )

    def get_memory(self, thread_id: str = "default") -> AnyConversationMemory:
        """Return the memory for *thread_id* (created on first access).

        New memories are built via the injected ``memory_factory``.  If
        ``max_threads`` is set, accessing a thread refreshes its LRU
        position and creating a new one evicts the least recently used
        memory.
        """
        memory = self._memories.get(thread_id)
        if memory is not None:
            self._memories.move_to_end(thread_id)
            return memory

        memory = self._memory_factory()
        self._memories[thread_id] = memory
        if self._max_threads is not None and len(self._memories) > self._max_threads:
            self._memories.popitem(last=False)
        return memory

    def clear_memory(self, thread_id: str) -> None:
        """Drop the memory for *thread_id* (no-op if unknown).

        Callers should invoke this when a conversation ends so the
        pipeline does not retain its entities indefinitely.  Only drops
        the in-RAM memory; use ``forget_thread`` to also purge the cache
        backend.
        """
        self._memories.pop(thread_id, None)

    def clear_all_memories(self) -> None:
        """Drop every conversation memory tracked by the pipeline."""
        self._memories.clear()

    def get_resolved_entities(self, thread_id: str = "default") -> list[Entity]:
        """All entities from the thread's memory, merged then first-seen ordered.

        The entity resolver may merge entities and sorts its output by
        span position; positions come from different messages, so that
        order is meaningless here and, worse, unstable (a new entity
        early in its message would steal the counter of an older one).
        Re-rank by first-seen order from memory so counter-based
        factories assign stable tokens for the whole conversation.
        """
        all_entities = self.get_memory(thread_id).all_entities
        if not all_entities:
            return []
        rank = {e.canonical_key: i for i, e in enumerate(all_entities)}
        fallback = len(rank)
        resolved = self._entity_resolver.resolve(all_entities)
        resolved.sort(
            # (d.text.lower(), d.label) is Entity.canonical_key, derived per
            # detection; min keeps a merged group at its earliest-seen rank.
            key=lambda e: min(
                rank.get((d.text.lower(), d.label), fallback) for d in e.detections
            )
        )
        return resolved

    # ------------------------------------------------------------------
    # Cache key helpers — prefix with thread_id for isolation
    # ------------------------------------------------------------------

    @staticmethod
    def _thread_key(thread_id: str, key: str) -> str:
        """Prefix a cache key with the given thread id."""
        return f"{thread_id}:{key}"

    @staticmethod
    def _memory_key(thread_id: str) -> str:
        """Cache key holding the serialized conversation memory snapshot."""
        return f"{thread_id}:piighost:memory"

    @staticmethod
    def _key_index_key(thread_id: str) -> str:
        """Cache key listing every thread-scoped key the pipeline wrote."""
        return f"{thread_id}:piighost:keys"

    async def _cache_set_indexed(self, thread_id: str, key: str, value: Any) -> None:
        """Write *key* and register it in the thread's key index.

        The index is what makes ``forget_thread`` possible on backends
        without prefix deletion (aiocache has no portable scan). The
        index carries a long TTL (``cache_ttl * 24``), refreshed on every
        index write: this bounds index growth for deployments that never
        call ``forget_thread`` while staying far longer than the data TTL
        so ``forget_thread`` still finds keys whose entries already
        expired.  With ``cache_ttl=None`` the index keeps ``ttl=None``
        because data never expires either.  The index is deleted by
        ``forget_thread`` and bounded by the number of distinct texts in
        the conversation.

        The read-modify-write on the index is racy under concurrency; the
        in-process race is closed by a per-thread ``asyncio.Lock``.  The
        residual CROSS-WORKER index race cannot be closed without
        backend-native sets and is TTL-bounded: orphaned entries expire
        with ``cache_ttl``; with ``cache_ttl=None`` the guarantee
        requires a single writer per thread.
        """
        await self._cache.set(key, value, ttl=self._cache_ttl)
        index_key = self._key_index_key(thread_id)
        async with self._index_locks[thread_id]:
            index: list[str] = await self._cache.get(index_key) or []
            if key not in index:
                index.append(key)
            # Refresh the index TTL even when the key was already listed.
            await self._cache.set(index_key, index, ttl=self._index_ttl)

    async def forget_thread(self, thread_id: str) -> None:
        """Erase every trace of *thread_id*: RAM memory and cache entries.

        Intended for end-of-conversation cleanup and right-to-be-forgotten
        requests (used by piighost-api). Idempotent.

        Raises on backend failure; deletion order (data keys first, index
        last) makes a retry complete the purge.
        """
        index_key = self._key_index_key(thread_id)
        index: list[str] = await self._cache.get(index_key) or []
        for key in index:
            await self._cache.delete(key)
        # The snapshot key is deterministic: delete it even when a lost
        # index write left it unlisted, so no memory snapshot survives.
        await self._cache.delete(self._memory_key(thread_id))
        await self._cache.delete(index_key)
        self._memories.pop(thread_id, None)
        self._index_locks.pop(thread_id, None)

    async def _hydrate_memory(self, thread_id: str) -> None:
        """Merge the cached memory snapshot for *thread_id* into RAM.

        Called at the top of every async entry point so a worker that
        did not process earlier messages still sees the entities (and
        therefore the first-seen token ordering) recorded by another
        worker through the shared cache backend.  Replay is idempotent;
        concurrent writers are last-write-wins, which is acceptable for
        alternating turns of a single conversation.
        """
        snapshot = await self._cache.get(self._memory_key(thread_id))
        if snapshot is not None:
            self.get_memory(thread_id).merge_snapshot(snapshot)

    async def _persist_memory(self, thread_id: str) -> None:
        """Write the thread's memory snapshot through to the cache backend."""
        memory = self.get_memory(thread_id)
        await self._cache_set_indexed(
            thread_id, self._memory_key(thread_id), memory.to_dict()
        )

    async def override_detections(
        self,
        text: str,
        detections: list[Detection],
        thread_id: str = "default",
    ) -> None:
        """Override cached detection results for user corrections.

        Overwrites the detection cache entry for the given text so that
        subsequent calls to ``anonymize()`` use the corrected detections
        instead of re-running the detector. Also invalidates any cached
        anonymize result for the same text so the next ``anonymize``
        call actually re-runs the pipeline (and emits an observation
        trace) instead of returning the stale pre-correction result.

        Emits a flat ``piighost.hitl_correction`` root span (when an
        observation backend is configured). The span carries:

        * ``input.text``: the original user text, **not redacted**, so a
          downstream dataset extractor can recover entities by slicing
          this text with the recorded positions.
        * ``input.labels``: the label vocabulary advertised by the
          underlying detector when it exposes a ``labels`` attribute,
          empty list otherwise.
        * ``input.detections``: the model detections (positions + labels +
          confidence + redacted text) read from the prior cache.
        * ``output.detections``: the human-corrected detections in the
          same shape.

        The trace deliberately includes the raw input text so HITL traces
        can be exported as a NER training dataset. Configure observation
        accordingly (PII may transit your observation backend). The span
        is best-effort: a failing backend never breaks the cache update.

        Args:
            text: The original text whose detections should be overridden.
            detections: The corrected list of detections.
            thread_id: Thread identifier for cache isolation.

        Raises:
            RuntimeError: If no cache backend is configured.
        """
        if self._cache is None:
            raise RuntimeError("Cannot override detections without a cache backend")

        await self._hydrate_memory(thread_id)

        detect_key = self._thread_key(
            thread_id, f"{CACHE_KEY_DETECTION}:{hash_sha256(text)}"
        )
        anon_result_key = self._thread_key(
            thread_id, f"{CACHE_KEY_ANON_RESULT}:{hash_sha256(text)}"
        )

        # Read the prior model detections so the HITL trace can carry the
        # before/after pair. Empty list when nothing was cached before.
        prior = await self._cache.get(detect_key)
        before: list[Detection] = (
            self._deserialize_detections(prior) if prior is not None else []
        )

        try:
            with self._observation.start_as_current_span(
                name="piighost.hitl_correction",
                session_id=thread_id if thread_id != "default" else None,
                tags=["hitl"],
            ) as span:
                detector_labels = getattr(self._detector, "labels", None)
                span.update(
                    input={
                        "text": text,
                        "labels": list(detector_labels) if detector_labels else [],
                        "detections": self._obs_detections_to_dicts(before),
                    },
                    output={"detections": self._obs_detections_to_dicts(detections)},
                )
        except Exception:
            logger.warning(
                "HITL observation failed during override_detections; "
                "continuing with cache update.",
                exc_info=True,
            )

        value = self._serialize_detections(detections)
        await self._cache_set_indexed(thread_id, detect_key, value)
        await self._cache.delete(anon_result_key)

    async def _cached_detect(self, text: str) -> list[Detection]:
        """Detect entities, using thread-scoped cache if available."""
        if self._cache is None:
            return await self._detector.detect(text)

        thread_id = _current_thread_id.get()
        cache_key = self._thread_key(
            thread_id, f"{CACHE_KEY_DETECTION}:{hash_sha256(text)}"
        )
        cached = await self._cache.get(cache_key)

        if cached is not None:
            return self._deserialize_detections(cached)

        detections = await self._detector.detect(text)
        value = self._serialize_detections(detections)
        await self._cache_set_indexed(thread_id, cache_key, value)
        return detections

    async def _store_mapping(
        self,
        original: str,
        anonymized: str,
        entities: list[Entity],
    ) -> None:
        """Store anonymization mapping under a thread-scoped key."""
        if self._cache is None:
            return

        thread_id = _current_thread_id.get()
        serialized_entities = self._serialize_entities(entities)
        key = self._thread_key(
            thread_id, f"{CACHE_KEY_ANONYMIZATION}:{hash_sha256(anonymized)}"
        )

        await self._cache_set_indexed(
            thread_id,
            key,
            {
                "original": original,
                "entities": serialized_entities,
            },
        )

    async def _cache_get_anon_result(self, text: str) -> dict | None:
        """Look up the cached anonymize result under a thread-scoped key."""
        if self._cache is None:
            return None
        thread_id = _current_thread_id.get()
        key = self._thread_key(
            thread_id, f"{CACHE_KEY_ANON_RESULT}:{hash_sha256(text)}"
        )
        return await self._cache.get(key)

    async def _store_anon_result(
        self,
        original: str,
        anonymized: str,
        entities: list[Entity],
    ) -> None:
        """Store ``original → (anonymized, entities)`` under a thread-scoped key."""
        if self._cache is None:
            return
        thread_id = _current_thread_id.get()
        key = self._thread_key(
            thread_id, f"{CACHE_KEY_ANON_RESULT}:{hash_sha256(original)}"
        )
        await self._cache_set_indexed(
            thread_id,
            key,
            {
                "anonymized": anonymized,
                "entities": self._serialize_entities(entities),
            },
        )

    # ------------------------------------------------------------------
    # Anonymize / deanonymize
    # ------------------------------------------------------------------

    async def deanonymize(
        self,
        anonymized_text: str,
        thread_id: str = "default",
    ) -> tuple[str, list[Entity]]:
        """Return the cached original text directly.

        The base pipeline reconstructs the original via span-based
        replacement, but in a conversation context entity detections
        carry positions from *different* messages.  Using the cached
        original avoids mismatches.

        Args:
            anonymized_text: The anonymized text to restore.
            thread_id: Thread identifier for cache isolation.

        Returns:
            The original text and the entities used for anonymization.

        Raises:
            CacheMissError: If *anonymized_text* was never produced
                by this pipeline.
        """
        from piighost.exceptions import CacheMissError

        key = self._thread_key(
            thread_id, f"{CACHE_KEY_ANONYMIZATION}:{hash_sha256(anonymized_text)}"
        )
        cached = await self._cache_get(key)

        if cached is None:
            raise CacheMissError(f"No anonymization mapping cached for hash {key!r}")

        entities = self._deserialize_entities(cached["entities"])
        return cached["original"], entities

    async def anonymize(
        self,
        text: str,
        thread_id: str = "default",
        *,
        metadata: Mapping[str, Any] | None = None,
        root_span: AbstractSpan | None = None,
    ) -> tuple[str, list[Entity]]:
        """Run detection, record entities in memory, then anonymize.

        Uses ``all_entities`` from memory for token creation so that
        counters stay consistent across messages.

        Args:
            text: The original text to anonymize.
            thread_id: Thread identifier for memory and cache isolation.
            metadata: Optional metadata forwarded to the observation trace.
            root_span: Caller-supplied root span. When provided the pipeline
                nests its stage observations under it and does not create a
                new root span from the configured observation service. When
                the result is already cached, the pipeline returns it without
                emitting any stage observations, including on a caller-supplied
                root span.

        Returns:
            A tuple of (anonymized text, entities used for anonymization).
        """
        token = _current_thread_id.set(thread_id)
        try:
            await self._hydrate_memory(thread_id)

            # Skip the pipeline run and the observation span when the
            # mapping is already cached for this (text, thread_id). The
            # entry is populated either by a previous ``anonymize`` for
            # the same text or by ``deanonymize_with_ent`` (which knows
            # both forms). Memory is updated so cross-message linking
            # still has the entities available even though the link
            # stage is skipped.
            cached = await self._cache_get_anon_result(text)
            if cached is not None:
                entities = self._deserialize_entities(cached["entities"])
                await self._record_entities(text, entities)
                return cached["anonymized"], entities

            if root_span is not None:
                return await self._anonymize_with_span(text, root_span)

            # Root span input is filled in retroactively from
            # ``_anonymize_with_span`` once detections are available, so
            # the observation factory can render the obs-redacted form
            # rather than swallowing the whole text under one sentinel.
            with self._observation.start_as_current_span(
                name="piighost.anonymize_pipeline",
                session_id=thread_id if thread_id != "default" else None,
                metadata=dict(metadata) if metadata else None,
            ) as auto_root:
                return await self._anonymize_with_span(text, auto_root)
        finally:
            _current_thread_id.reset(token)

    # ------------------------------------------------------------------
    # Stage hooks (called by the base class template _anonymize_with_span)
    # ------------------------------------------------------------------

    def _link_stage(self, text: str, detections: list[Detection]) -> list[Entity]:
        """Single-text linking plus cross-message linking against memory."""
        thread_id = _current_thread_id.get()
        entities = super()._link_stage(text, detections)
        return self._entity_linker.link_entities(
            entities,
            self.get_memory(thread_id).all_entities,
        )

    async def _record_entities(self, text: str, entities: list[Entity]) -> None:
        thread_id = _current_thread_id.get()
        memory = self.get_memory(thread_id)
        changed = memory.record(hash_sha256(text), entities)
        # Legacy memories typed against the old "-> None" record signature
        # must keep the persist-always behaviour (None is not False).
        if changed is not False:
            await self._persist_memory(thread_id)
            return
        # Re-publish after backend expiry: the snapshot must exist whenever
        # this worker holds entities, or a fresh worker would renumber the
        # conversation and swap identities across workers.
        if memory.all_entities and (
            await self._cache.get(self._memory_key(thread_id)) is None
        ):
            await self._persist_memory(thread_id)

    def _resolved_token_pairs(
        self, thread_id: str
    ) -> tuple[dict[Entity, str], list[tuple[str, str]]]:
        """Token map for the thread's resolved entities plus replacement pairs.

        Resolution and token creation are computed once here and shared
        by ``_render_stage`` and ``anonymize_with_ent`` so a single
        anonymize run does not resolve the conversation twice.
        """
        resolved = self.get_resolved_entities(thread_id)
        if not resolved:
            return {}, []
        token_map = self.ph_factory.create(resolved)
        pairs = [
            (detection.text, token)
            for entity, token in token_map.items()
            for detection in entity.detections
        ]
        return token_map, pairs

    def _render_stage(self, text: str, entities: list[Entity]) -> tuple[str, list[str]]:
        """Render via the conversation-wide replacement pass.

        Conversation entities carry detection positions from other
        messages, so span-based replacement does not apply; the
        longest-first word-boundary pass over all known surface forms
        is used instead.

        The ``entities`` parameter is intentionally unused: rendering uses
        the full conversation memory recorded by ``_record_entities``, not
        the per-message entities passed in.
        """
        thread_id = _current_thread_id.get()
        token_map, pairs = self._resolved_token_pairs(thread_id)
        return (
            _replace_longest_first(text, pairs, word_boundary=True),
            list(token_map.values()),
        )

    async def deanonymize_with_ent(
        self,
        text: str,
        thread_id: str = "default",
    ) -> str:
        """Replace all known tokens with original values in a single pass.

        Works on any text containing tokens, even text never anonymized
        by this pipeline (e.g. LLM-generated output, tool arguments).
        Tokens are replaced **longest-first** to avoid partial matches.

        The result is stored in the cache so that ``deanonymize()`` can
        look it up later.

        Args:
            text: Text potentially containing placeholder tokens.
            thread_id: Thread identifier for memory and cache isolation.

        Returns:
            Text with tokens replaced by original values.
        """
        await self._hydrate_memory(thread_id)

        token_map, _ = self._resolved_token_pairs(thread_id)

        if not token_map:
            return text

        pairs = [
            (token, entity.detections[0].text) for entity, token in token_map.items()
        ]
        resolved = list(token_map.keys())

        anonymized = text
        restored = _replace_longest_first(text, pairs)

        cv_token = _current_thread_id.set(thread_id)
        try:
            await self._store_mapping(restored, anonymized, resolved)
            await self._store_anon_result(restored, anonymized, resolved)
        finally:
            _current_thread_id.reset(cv_token)
        return restored

    def anonymize_with_ent(
        self,
        text: str,
        thread_id: str = "default",
    ) -> str:
        """Replace all known original values with tokens in a single pass.

        Replaces **all** spelling variants of each entity (not just the
        canonical form).  Values are replaced **longest-first** to avoid
        partial matches.

        Operates on the in-RAM memory of this worker; in multi-worker
        deployments call an async entry point (``anonymize`` /
        ``deanonymize_with_ent``) first so memory is hydrated from the
        shared cache.

        Args:
            text: Text potentially containing original PII values.
            thread_id: Thread identifier for memory isolation.

        Returns:
            Text with original values replaced by tokens.
        """
        _, pairs = self._resolved_token_pairs(thread_id)
        return _replace_longest_first(text, pairs, word_boundary=True)
