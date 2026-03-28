import hashlib
from collections import defaultdict
from typing import Protocol

from piighost.models import Entity


class AnyPlaceholderFactory(Protocol):
    """Protocol defining the interface for placeholder factories.

    A placeholder factory takes a list of entities and returns
    a mapping from each entity to its replacement token.
    """

    def create(self, entities: list[Entity]) -> dict[Entity, str]:
        """Create replacement tokens for all entities at once.

        Args:
            entities: The entities to create tokens for.

        Returns:
            A dict mapping each entity to its replacement token.
        """
        ...


class CounterPlaceholderFactory:
    """Factory that generates tokens like ``<<PERSON_1>>``, ``<<PERSON_2>>``.

    Each entity gets a unique counter per label. Two different PERSON
    entities get ``<<PERSON_1>>`` and ``<<PERSON_2>>``, while a LOCATION
    entity gets ``<<LOCATION_1>>``.

    Example:
        >>> from piighost.models import Detection, Entity, Span
        >>> factory = CounterPlaceholderFactory()
        >>> e = Entity(detections=(Detection(text="Patrick", label="PERSON", position=Span(0, 7), confidence=0.9),))
        >>> factory.create([e])[e]
        '<<PERSON_1>>'
    """

    def create(self, entities: list[Entity]) -> dict[Entity, str]:
        """Create counter-based tokens for all entities.

        Args:
            entities: The entities to create tokens for.

        Returns:
            A dict mapping each entity to a token like ``"<<PERSON_1>>"``.
        """
        result: dict[Entity, str] = {}
        counters: dict[str, int] = defaultdict(int)

        for entity in entities:
            label = entity.label
            counters[label] += 1
            result[entity] = f"<<{label}_{counters[label]}>>"

        return result


class HashPlaceholderFactory:
    """Factory that generates tokens like ``<PERSON:a1b2c3d4>``.

    Uses SHA-256 of the canonical text + label to produce a deterministic,
    opaque token. Same entity always produces the same hash.

    Args:
        hash_length: Number of hex characters to use from the hash.
            Defaults to 8.

    Example:
        >>> from piighost.models import Detection, Entity, Span
        >>> factory = HashPlaceholderFactory()
        >>> e = Entity(detections=(Detection(text="Patrick", label="PERSON", position=Span(0, 7), confidence=0.9),))
        >>> token = factory.create([e])[e]
        >>> token.startswith('<PERSON:') and token.endswith('>')
        True
    """

    _hash_length: int

    def __init__(self, hash_length: int = 8) -> None:
        self._hash_length = hash_length

    def create(self, entities: list[Entity]) -> dict[Entity, str]:
        """Create hash-based tokens for all entities.

        Args:
            entities: The entities to create tokens for.

        Returns:
            A dict mapping each entity to a token like ``"<PERSON:a1b2c3d4>"``.
        """
        result: dict[Entity, str] = {}

        for entity in entities:
            canonical_text = entity.detections[0].text.lower()
            label = entity.label
            raw = f"{canonical_text}:{label}"
            digest = hashlib.sha256(raw.encode()).hexdigest()[: self._hash_length]
            result[entity] = f"<{label}:{digest}>"

        return result


class RedactPlaceholderFactory:
    """Factory that generates tokens like ``<PERSON>``.

    All entities with the same label share the same token there is
    no discrimination between different PIIs of the same type.
    Reversible because ``deanonymize`` receives the entities with
    their original positions.

    Example:
        >>> from piighost.models import Detection, Entity, Span
        >>> factory = RedactPlaceholderFactory()
        >>> e = Entity(detections=(Detection(text="Patrick", label="PERSON", position=Span(0, 7), confidence=0.9),))
        >>> factory.create([e])[e]
        '<PERSON>'
    """

    def create(self, entities: list[Entity]) -> dict[Entity, str]:
        """Create redact tokens for all entities.

        Args:
            entities: The entities to create tokens for.

        Returns:
            A dict mapping each entity to a token like ``"<PERSON>"``.
        """
        return {entity: f"<{entity.label}>" for entity in entities}
