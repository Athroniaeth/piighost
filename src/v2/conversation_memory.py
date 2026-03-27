"""Conversation-scoped memory for accumulating entities across messages.

Stores all :class:`Entity` objects seen during a conversation, indexed
by message hash and deduplicated by ``(text.lower(), label)``.  The
``all_entities`` property returns a flat, append-only list used by the
pipeline to recreate consistent placeholder tokens across messages.
"""

from dataclasses import dataclass, field
from typing import Protocol

from v2.models import Entity


class AnyConversationMemory(Protocol):
    """Protocol for conversation memory implementations."""

    entities_by_hash: dict[str, list[Entity]]

    @property
    def all_entities(self) -> list[Entity]: ...

    def record(self, text_hash: str, entities: list[Entity]) -> None: ...


@dataclass
class ConversationMemory:
    """In-memory conversation memory that accumulates entities across messages.

    Entities are stored per message hash and deduplicated by canonical
    identity ``(text.lower(), label)``.  The ``all_entities`` property
    flattens all stored entities in insertion order, skipping duplicates.

    Example:
        >>> from v2.models import Detection, Entity, Span
        >>> memory = ConversationMemory()
        >>> e = Entity(detections=(Detection("Patrick", "PERSON", Span(0, 7), 0.9),))
        >>> memory.record("abc123", [e])
        >>> memory.all_entities
        [Entity(detections=(Detection(text='Patrick', label='PERSON', position=Span(start_pos=0, end_pos=7), confidence=0.9),))]
    """

    entities_by_hash: dict[str, list[Entity]] = field(default_factory=dict)

    def record(self, text_hash: str, entities: list[Entity]) -> None:
        """Record entities for a message, deduplicating against known ones.

        Args:
            text_hash: SHA-256 hash of the original text.
            entities: Entities detected in that message.
        """
        new_entities = [e for e in entities if not self._is_known(e)]
        if text_hash in self.entities_by_hash:
            self.entities_by_hash[text_hash].extend(new_entities)
        else:
            self.entities_by_hash[text_hash] = new_entities

    @property
    def all_entities(self) -> list[Entity]:
        """Flat deduplicated list of all entities, in insertion order."""
        seen: set[tuple[str, str]] = set()
        result: list[Entity] = []
        for entities in self.entities_by_hash.values():
            for entity in entities:
                key = (entity.detections[0].text.lower(), entity.label)
                if key not in seen:
                    seen.add(key)
                    result.append(entity)
        return result

    def _is_known(self, entity: Entity) -> bool:
        """Check if a canonically identical entity already exists."""
        canonical = entity.detections[0].text.lower()
        label = entity.label
        return any(
            e.detections[0].text.lower() == canonical and e.label == label
            for entities in self.entities_by_hash.values()
            for e in entities
        )
