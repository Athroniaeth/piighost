import asyncio
import importlib.util
import warnings
from typing import Any, Generic, Mapping, Tuple

from typing_extensions import TypeVar

if importlib.util.find_spec("aiocache") is None:
    raise ImportError(
        "AnonymizationPipeline requires aiocache for caching. Install with `uv add piighost[cache]`."
    )

from aiocache import BaseCache, SimpleMemoryCache

from piighost.anonymizer import Anonymizer, AnyAnonymizer
from piighost.detector import AnyDetector
from piighost.exceptions import CacheMissError, PIIGhostConfigWarning, PIIRemainingError
from piighost.guard import AnyGuardRail, DisabledGuardRail
from piighost.linker.entity import AnyEntityLinker, ExactEntityLinker
from piighost.models import Detection, Entity
from piighost.observation.base import (
    AbstractObservationService,
    AbstractSpan,
    NoOpObservationService,
)
from piighost.placeholder import AnyPlaceholderFactory
from piighost.placeholder_tags import PlaceholderPreservation
from piighost.resolver.entity import (
    AnyEntityConflictResolver,
    MergeEntityConflictResolver,
)
from piighost.resolver.span import (
    AnySpanConflictResolver,
    ConfidenceSpanConflictResolver,
)
from piighost.utils import hash_sha256

PreservationT = TypeVar(
    "PreservationT",
    bound=PlaceholderPreservation,
    default=PlaceholderPreservation,
)
"""Preservation tag carried by the pipeline's anonymiser factory."""

CACHE_KEY_DETECTION = "detect"
"""Prefix for detector-result cache entries."""

CACHE_KEY_ANONYMIZATION = "anon:anonymized"
"""Prefix for anonymized-text → (original, entities) cache entries."""

CACHE_KEY_ANON_RESULT = "anon:result"
"""Prefix for original-text → (anonymized, entities) cache entries.

Populated on every successful ``anonymize`` and on every ``deanonymize``
(both directions of the mapping become known at deanonymize time). Lets
``anonymize`` short-circuit pipeline execution and observation when the
mapping for *text* is already known, which is the common case for the
LangChain middleware which re-anonymises the full message history at
every conversation turn."""


def _detection_to_dict(d: Detection, *, token: str | None = None) -> dict[str, Any]:
    """Serialize a Detection to a JSON-friendly dict for observation output.

    When *token* is provided, the detection's surface text is replaced
    with the token. Used to keep raw PII out of observation payloads.
    """
    return {
        "label": d.label,
        "position": [d.position.start_pos, d.position.end_pos],
        "confidence": d.confidence,
        "text": token if token is not None else d.text,
    }


def _entity_to_dict(e: Entity, *, token: str | None = None) -> dict[str, Any]:
    """Serialize an Entity to a JSON-friendly dict for observation output.

    When *token* is provided, every detection's surface text is replaced
    with the same token (the obs-side placeholder for the entity).
    """
    return {
        "label": e.label,
        "detections": [_detection_to_dict(d, token=token) for d in e.detections],
    }


class AnonymizationPipeline(Generic[PreservationT]):
    """Orchestrates the full anonymization pipeline.

    Chains all components together: detect → resolve spans → link entities
    → resolve entities → anonymize. Uses aiocache for:
    - Detector results (avoid expensive NER re-computation)
    - Anonymization mappings (allow deanonymize without passing entities)

    Cache keys use prefixes to avoid collisions:
    - ``detect:<hash>`` detector results
    - ``anon:anonymized:<hash>`` anonymized text → (original, entities)

    Args:
        detector: The entity detector (async).
        span_resolver: Resolves overlapping detection spans.
        entity_linker: Expands and groups detections into entities.
        entity_resolver: Merges conflicting entities.
        anonymizer: Performs text replacement and deanonymization.
        guard_rail: Optional final stage that re-validates the
            anonymized text. Defaults to ``DisabledGuardRail`` (no-op).
            Pass a ``DetectorGuardRail`` (or any ``AnyGuardRail``) to
            raise ``PIIRemainingError`` whenever residual PII is found
            in the output.
        cache: Optional aiocache instance. If ``None``, no caching
            is performed and deanonymize will raise KeyError.
        cache_ttl: Time-to-live in seconds applied to every cache entry
            the pipeline writes.  ``None`` (default) keeps entries until
            the backend evicts them, which is fine for in-memory caches
            but can leak unbounded state when sharing a Redis backend
            across threads.
        observation: Observation backend used to emit the per-stage
            trace tree.  Defaults to ``NoOpObservationService`` (silent,
            zero-overhead).
        observation_ph_factory: Placeholder factory used to render PII
            in observation payloads. Defaults to ``None`` (raw text, no
            redaction), which keeps observation traces extractable for
            HITL dataset workflows. When set to an ``AnyPlaceholderFactory``,
            observation payloads are redacted and a ``PIIGhostConfigWarning``
            fires once at init describing the trade-off (raw PII safety vs.
            dataset extraction loss).
    """

    _detector: AnyDetector
    _span_resolver: AnySpanConflictResolver
    _entity_linker: AnyEntityLinker
    _entity_resolver: AnyEntityConflictResolver
    _anonymizer: AnyAnonymizer[PreservationT]
    _guard_rail: AnyGuardRail
    _cache: BaseCache
    _cache_ttl: int | None
    _observation: AbstractObservationService
    _obs_ph_factory: AnyPlaceholderFactory | None
    _obs_anonymizer: Anonymizer | None

    def __init__(
        self,
        detector: AnyDetector,
        anonymizer: AnyAnonymizer[PreservationT],
        span_resolver: AnySpanConflictResolver | None = None,
        entity_linker: AnyEntityLinker | None = None,
        entity_resolver: AnyEntityConflictResolver | None = None,
        guard_rail: AnyGuardRail | None = None,
        cache: BaseCache | None = None,
        cache_ttl: int | None = None,
        observation: AbstractObservationService | None = None,
        observation_ph_factory: AnyPlaceholderFactory | None = None,
    ) -> None:
        span_resolver = span_resolver or ConfidenceSpanConflictResolver()
        entity_linker = entity_linker or ExactEntityLinker()
        entity_resolver = entity_resolver or MergeEntityConflictResolver()
        guard_rail = guard_rail or DisabledGuardRail()

        self._detector = detector
        self._span_resolver = span_resolver
        self._entity_linker = entity_linker
        self._entity_resolver = entity_resolver
        self._anonymizer = anonymizer
        self._guard_rail = guard_rail
        self._cache = cache or SimpleMemoryCache()
        self._cache_ttl = cache_ttl
        self._observation = observation or NoOpObservationService()

        # Observation redaction is opt-in. None (the default) keeps raw
        # text in observation traces, which is required for downstream
        # HITL dataset extraction. An explicit factory restores the
        # historical redact behaviour but breaks dataset extraction;
        # warn the operator so the trade-off is conscious.
        if observation_ph_factory is not None:
            warnings.warn(
                "observation_ph_factory is set, so observation traces "
                "will be redacted via this factory. With redaction, "
                "the raw user text is no longer recoverable from the "
                "observation backend, which makes traces unsuitable as "
                "input for HITL dataset extraction or NER evaluation. "
                "Pass observation_ph_factory=None (the default) to keep "
                "raw text in traces, or accept the redaction trade-off "
                "if PII must not transit the observation backend.",
                PIIGhostConfigWarning,
                stacklevel=2,
            )
            self._obs_ph_factory: AnyPlaceholderFactory | None = observation_ph_factory
            self._obs_anonymizer: Anonymizer | None = Anonymizer(
                ph_factory=observation_ph_factory
            )
        else:
            self._obs_ph_factory = None
            self._obs_anonymizer = None

    @property
    def ph_factory(self) -> AnyPlaceholderFactory[PreservationT]:
        """The placeholder factory used by the anonymizer."""
        return self._anonymizer.ph_factory

    def _obs_tokens_for_detections(
        self, detections: list[Detection]
    ) -> dict[Detection, str]:
        """Render one observation token per detection.

        Each detection is wrapped in a one-detection ``Entity`` so the
        observation factory can produce a token, then the result is
        flipped back to a ``Detection -> token`` mapping.

        Returns an empty dict when no obs factory is configured.
        """
        if self._obs_ph_factory is None:
            return {}
        fake_entities = [Entity(detections=(d,)) for d in detections]
        ent_tokens = self._obs_ph_factory.create(fake_entities)
        return {ent.detections[0]: token for ent, token in ent_tokens.items()}

    def _obs_text(self, text: str, entities: list[Entity]) -> str:
        """Return *text* either raw (no obs factory) or redacted via the obs factory.

        Used to populate the ``input.text`` / ``output.text`` of root and
        child observation spans without leaking raw PII when the operator
        opted into redaction.
        """
        if self._obs_anonymizer is None:
            return text
        return self._obs_anonymizer.anonymize(text, entities)

    def _obs_detections_to_dicts(
        self, detections: list[Detection]
    ) -> list[dict[str, Any]]:
        """Render a list of detections for observation, redacted or raw per config.

        When the obs factory is set, this preserves cross-detection
        numbering (e.g. counter-based factories will emit <<PERSON:1>>,
        <<PERSON:2>>, ...) by tokenising the whole list in one pass
        instead of once per detection.
        """
        if self._obs_anonymizer is None:
            return [_detection_to_dict(d) for d in detections]
        token_map = self._obs_tokens_for_detections(detections)
        return [_detection_to_dict(d, token=token_map[d]) for d in detections]

    async def detect_entities(self, text: str) -> list[Entity]:
        """Run the detection pipeline: detect → resolve → link → resolve.

        Args:
            text: The text to analyze.

        Returns:
            Resolved and merged entities found in the text.
        """
        detections = await self._cached_detect(text)
        detections = self._span_resolver.resolve(detections)
        entities = self._entity_linker.link(text, detections)
        return self._entity_resolver.resolve(entities)

    async def anonymize(
        self,
        text: str,
        *,
        metadata: Mapping[str, Any] | None = None,
        root_span: AbstractSpan | None = None,
    ) -> Tuple[str, list[Entity]]:
        """Run the full pipeline: detect → resolve → link → resolve → anonymize.

        Args:
            text: The original text to anonymize.
            metadata: Optional metadata forwarded to the observation trace.
            root_span: Caller-supplied root span. When provided the pipeline
                nests its stage observations under it and does not create a
                new root span from the configured observation service.

        Returns:
            A tuple of (anonymized text, entities used for anonymization).

        Raises:
            PIIRemainingError: If a non-default guard rail detects
                residual PII in the anonymized output.
        """
        if root_span is not None:
            return await self._anonymize_with_span(text, root_span)

        # Skip both the pipeline run and the observation span when the
        # mapping for *text* is already cached. The mapping was either
        # produced by a previous ``anonymize`` call for the same text or
        # populated by ``deanonymize`` (which knows both forms).
        cached = await self._cache_get_anon_result(text)
        if cached is not None:
            entities = self._deserialize_entities(cached["entities"])
            return cached["anonymized"], entities

        # The root span's input is filled in retroactively from inside
        # ``_anonymize_with_span`` once detections are available, so the
        # observation factory can render the obs-redacted form rather
        # than swallowing the whole text under one sentinel.
        with self._observation.start_as_current_span(
            name="piighost.anonymize_pipeline",
            metadata=dict(metadata) if metadata else None,
        ) as auto_root:
            return await self._anonymize_with_span(text, auto_root)

    async def _obs_pause(self) -> None:
        """Space consecutive stage observations by ~1 ms when the backend asks.

        Non-blocking (``asyncio.sleep``), and skipped entirely for
        backends that do not set ``needs_timestamp_spacing`` (NoOp).
        See ``AbstractObservationService.needs_timestamp_spacing``.
        """
        if getattr(self._observation, "needs_timestamp_spacing", False):
            await asyncio.sleep(0.001)

    def _link_stage(self, text: str, detections: list[Detection]) -> list[Entity]:
        """Link detections into entities and resolve conflicts.

        Subclasses extend this to add cross-message linking.
        """
        entities = self._entity_linker.link(text, detections)
        return self._entity_resolver.resolve(entities)

    async def _record_entities(self, text: str, entities: list[Entity]) -> None:
        """Hook called after linking; the base pipeline keeps no memory."""
        return None

    def _render_stage(self, text: str, entities: list[Entity]) -> tuple[str, list[str]]:
        """Render the anonymized text; returns ``(anonymized, tokens)``.

        Tokens are forwarded to the guard rail so it can ignore the
        placeholders the pipeline itself just emitted.
        """
        token_map = self.ph_factory.create(entities)
        return self._anonymizer.anonymize(text, entities), list(token_map.values())

    async def _anonymize_with_span(
        self,
        text: str,
        root_span: AbstractSpan,
    ) -> Tuple[str, list[Entity]]:
        """Execute all pipeline stages, emitting child observations on *root_span*."""
        # Detect
        with root_span.start_as_current_observation(
            name="piighost.detect",
            as_type="tool",
        ) as span:
            detections = await self._cached_detect(text)
            obs_text_pre_link = self._obs_text(
                text, [Entity(detections=(d,)) for d in detections]
            )
            root_span.update(input={"text": obs_text_pre_link})
            span.update(
                input={"text": obs_text_pre_link},
                output={"detections": self._obs_detections_to_dicts(detections)},
            )
            detections = self._span_resolver.resolve(detections)
            await self._obs_pause()

        # Link
        with root_span.start_as_current_observation(
            name="piighost.link",
            as_type="span",
        ) as span:
            entities = self._link_stage(text, detections)
            ent_tokens = (
                self._obs_ph_factory.create(entities)
                if self._obs_ph_factory is not None
                else {}
            )
            span.update(
                input={"detections": self._obs_detections_to_dicts(detections)},
                output={
                    "entities": [
                        _entity_to_dict(e, token=ent_tokens[e] if ent_tokens else None)
                        for e in entities
                    ]
                },
            )
            await self._obs_pause()

        await self._record_entities(text, entities)

        # Placeholder
        with root_span.start_as_current_observation(
            name="piighost.placeholder",
            as_type="tool",
        ) as span:
            anonymized, tokens = self._render_stage(text, entities)
            obs_text = self._obs_text(text, entities)
            span.update(
                input={"text": obs_text, "entity_count": len(entities)},
                output={"text": anonymized},
            )
            await self._obs_pause()

        # Guard
        with root_span.start_as_current_observation(
            name="piighost.guard",
            as_type="guardrail",
        ) as span:
            span.update(input={"text": anonymized})
            try:
                await self._guard_rail.check(anonymized, tokens=tokens)
            except PIIRemainingError:
                span.update(output={"passed": False})
                raise
            span.update(output={"passed": True})
            await self._obs_pause()

        root_span.update(
            output={"text": anonymized, "entity_count": len(entities)},
        )

        await self._store_mapping(text, anonymized, entities)
        await self._store_anon_result(text, anonymized, entities)
        return anonymized, entities

    async def deanonymize(self, anonymized_text: str) -> Tuple[str, list[Entity]]:
        """Deanonymize using the anonymized text as lookup key.

        Args:
            anonymized_text: The anonymized text to restore.

        Returns:
            The restored original text.

        Raises:
            KeyError: If the anonymized text was never produced by this pipeline.
        """
        key = f"{CACHE_KEY_ANONYMIZATION}:{hash_sha256(anonymized_text)}"
        cached = await self._cache_get(key)

        if cached is None:
            raise CacheMissError(f"No anonymization mapping cached for hash {key!r}")

        entities = self._deserialize_entities(cached["entities"])
        result = self._anonymizer.deanonymize(anonymized_text, entities)
        # Both forms of the mapping are now known. Populate the inverse
        # cache so a subsequent ``anonymize(result)`` is a no-op (skips
        # pipeline + observation).
        await self._store_anon_result(result, anonymized_text, entities)
        return result, entities

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    async def _store_mapping(
        self,
        original: str,
        anonymized: str,
        entities: list[Entity],
    ) -> None:
        """Store the anonymization mapping in cache (both directions)."""
        if self._cache is None:
            return

        serialized_entities = self._serialize_entities(entities)
        key = f"{CACHE_KEY_ANONYMIZATION}:{hash_sha256(anonymized)}"

        await self._cache.set(
            key,
            {
                "original": original,
                "entities": serialized_entities,
            },
            ttl=self._cache_ttl,
        )

    async def _cache_get_anon_result(self, text: str) -> dict | None:
        """Return the cached anonymize result for *text*, or ``None``."""
        if self._cache is None:
            return None
        key = f"{CACHE_KEY_ANON_RESULT}:{hash_sha256(text)}"
        return await self._cache.get(key)

    async def _store_anon_result(
        self,
        original: str,
        anonymized: str,
        entities: list[Entity],
    ) -> None:
        """Store ``original → (anonymized, entities)`` in cache.

        Symmetric to ``_store_mapping``: where the latter keys on the
        anonymized text (so ``deanonymize`` can find it), this one keys
        on the original text so ``anonymize`` can short-circuit on a
        repeat call. Called from both ``anonymize`` (after a fresh run)
        and ``deanonymize`` (which produces both forms).
        """
        if self._cache is None:
            return
        key = f"{CACHE_KEY_ANON_RESULT}:{hash_sha256(original)}"
        await self._cache.set(
            key,
            {
                "anonymized": anonymized,
                "entities": self._serialize_entities(entities),
            },
            ttl=self._cache_ttl,
        )

    async def _cached_detect(self, text: str) -> list[Detection]:
        """Detect entities, using cache if available."""
        if self._cache is None:
            return await self._detector.detect(text)

        cache_key = f"{CACHE_KEY_DETECTION}:{hash_sha256(text)}"
        cached = await self._cache.get(cache_key)

        if cached is not None:
            return self._deserialize_detections(cached)

        detections = await self._detector.detect(text)
        value = self._serialize_detections(detections)
        await self._cache.set(cache_key, value, ttl=self._cache_ttl)
        return detections

    async def _cache_get(self, key: str) -> dict | None:
        """Get a value from cache, or None if no cache or key missing."""
        if self._cache is None:
            return None
        result = await self._cache.get(key)
        return result

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_detections(detections: list[Detection]) -> list[dict]:
        return [d.to_dict() for d in detections]

    @staticmethod
    def _deserialize_detections(data: list[dict]) -> list[Detection]:
        return [Detection.from_dict(d) for d in data]

    @staticmethod
    def _serialize_entities(entities: list[Entity]) -> list[list[dict]]:
        """Serialize entities as a list of detection lists."""
        return [[d.to_dict() for d in entity.detections] for entity in entities]

    @staticmethod
    def _deserialize_entities(data: list[list[dict]]) -> list[Entity]:
        """Deserialize entities from a list of detection lists."""
        return [
            Entity(detections=tuple(Detection.from_dict(d) for d in detections))
            for detections in data
        ]
