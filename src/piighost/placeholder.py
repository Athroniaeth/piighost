import hashlib
import re
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


class MaskPlaceholderFactory:
    """Factory that generates partially masked tokens preserving some original characters.

    Applies label-aware masking strategies:

    * **Email** labels: keeps the first character and domain
      (``j***@email.com``).
    * **Numeric** labels (credit card, phone, SSN, IBAN, …): keeps the
      last ``visible_chars`` digits (``****4567``).
    * **Default** (names, locations, …): keeps the first character and
      masks the rest (``P******``).

    Labels are matched case-insensitively.  A label is considered
    *email* if it contains ``"email"`` and *numeric* if it matches
    any entry in ``NUMERIC_LABELS``.

    Args:
        mask_char: Character used for masking.  Defaults to ``"*"``.
        visible_chars: Number of characters to keep visible for numeric
            masking.  Defaults to 4.

    Example:
        >>> from piighost.models import Detection, Entity, Span
        >>> factory = MaskPlaceholderFactory()
        >>> e = Entity(detections=(Detection(text="patrick@email.com", label="EMAIL", position=Span(0, 17), confidence=0.9),))
        >>> factory.create([e])[e]
        'p***@email.com'
    """

    NUMERIC_LABELS: frozenset[str] = frozenset(
        {
            "credit_card",
            "phone",
            "phone_international",
            "us_phone",
            "fr_phone",
            "de_phone",
            "ssn",
            "us_ssn",
            "fr_ssn",
            "iban",
            "eu_iban",
            "uk_nhs",
            "us_ein",
            "us_bank_routing",
            "ip_address",
        }
    )

    _mask_char: str
    _visible_chars: int

    def __init__(self, mask_char: str = "*", visible_chars: int = 4) -> None:
        self._mask_char = mask_char
        self._visible_chars = visible_chars

    def create(self, entities: list[Entity]) -> dict[Entity, str]:
        """Create partially masked tokens for all entities.

        Args:
            entities: The entities to create tokens for.

        Returns:
            A dict mapping each entity to a masked token.
        """
        return {entity: self._mask(entity) for entity in entities}

    def _mask(self, entity: Entity) -> str:
        text = entity.detections[0].text
        label_lower = entity.label.lower()

        if "email" in label_lower:
            return self._mask_email(text)

        if label_lower in self.NUMERIC_LABELS:
            return self._mask_numeric(text)

        return self._mask_default(text)

    def _mask_email(self, text: str) -> str:
        """``j***@email.com`` — keep first char of local part + domain."""
        match = re.match(r"^(.)(.*?)(@.+)$", text)
        if not match:
            return self._mask_default(text)
        first, middle, domain = match.groups()
        return first + self._mask_char * len(middle) + domain

    def _mask_numeric(self, text: str) -> str:
        """``****4567`` — keep last ``visible_chars`` digits."""
        digits = re.sub(r"\D", "", text)
        if len(digits) <= self._visible_chars:
            return text
        visible = digits[-self._visible_chars :]
        masked_count = len(digits) - self._visible_chars
        return self._mask_char * masked_count + visible

    def _mask_default(self, text: str) -> str:
        """``P******`` — keep first character, mask the rest."""
        if len(text) <= 1:
            return text
        return text[0] + self._mask_char * (len(text) - 1)
