"""Faker-based placeholder factory.

Generates realistic fake data as replacement tokens using the
`Faker <https://faker.readthedocs.io/>`_ library.  Each entity label
is mapped to a Faker provider method via a configurable strategies dict.
"""

import importlib.util
import zlib
from collections.abc import Callable
from typing import TYPE_CHECKING

from piighost.models import Entity

if TYPE_CHECKING:
    from piighost.config.models.placeholder import FakerPlaceholderConfig

if importlib.util.find_spec("faker") is None:
    raise ImportError(
        "You must install faker to use FakerPlaceholderFactory, "
        "please install piighost[faker]"
    )

from faker import Faker

from piighost.placeholder import AnyPlaceholderFactory
from piighost.placeholder_tags import PreservesLabeledIdentityFaker

FakerFn = Callable[[Faker], str]
"""Signature for faker functions: ``(faker_instance) -> fake_value``."""


def fake_person(faker: Faker) -> str:
    return faker.name()


def fake_location(faker: Faker) -> str:
    return faker.city()


def fake_email(faker: Faker) -> str:
    return faker.email()


def fake_phone(faker: Faker) -> str:
    return faker.phone_number()


def fake_credit_card(faker: Faker) -> str:
    return faker.credit_card_number()


def fake_ssn(faker: Faker) -> str:
    return faker.ssn()


def fake_iban(faker: Faker) -> str:
    return faker.iban()


def fake_ip_address(faker: Faker) -> str:
    return faker.ipv4()


def fake_url(faker: Faker) -> str:
    return faker.url()


def fake_address(faker: Faker) -> str:
    return faker.address()


def fake_country(faker: Faker) -> str:
    return faker.country()


DEFAULT_STRATEGIES: dict[str, FakerFn] = {
    "person": fake_person,
    "location": fake_location,
    "email": fake_email,
    "phone": fake_phone,
    "phone_international": fake_phone,
    "us_phone": fake_phone,
    "fr_phone": fake_phone,
    "de_phone": fake_phone,
    "credit_card": fake_credit_card,
    "ssn": fake_ssn,
    "us_ssn": fake_ssn,
    "fr_ssn": fake_ssn,
    "iban": fake_iban,
    "eu_iban": fake_iban,
    "ip_address": fake_ip_address,
    "url": fake_url,
    "address": fake_address,
    "country": fake_country,
}


class FakerPlaceholderFactory(AnyPlaceholderFactory[PreservesLabeledIdentityFaker]):
    """Factory that generates realistic fake data as replacement tokens.

    Uses a configurable ``strategies`` mapping from label (lowercase) to
    a function ``(Faker) -> str``.  Labels not present in the mapping
    produce a generic ``<LABEL>`` redacted token.

    The same entity always produces the same fake value within a single
    ``create()`` call (deterministic per entity via seeding).

    Each entity's fake value is derived deterministically by seeding the
    Faker instance from the entity's ``(canonical text, label)`` before
    generating, so the same entity always maps to the same value across
    calls, workers, and restarts (independent of RNG state). This is what
    makes the factory usable in a conversation: tokens stay reversible.

    Note:
        Faker values can still coincidentally collide with a real-world
        value (a generated name matching a real person), which the
        middleware cannot detect during string replacement. Prefer
        ``FakerHashPlaceholderFactory`` when collision-resistance matters.

    Args:
        faker: Optional pre-configured ``Faker`` instance.  Defaults to
            ``Faker()`` with no locale.
        strategies: Optional dict mapping lowercase labels to faker
            functions.  Replaces the built-in defaults when provided.
        seed: Optional value folded into the per-entity seed so two
            factories configured with different seeds produce different
            (but each internally deterministic) values.

    Example:
        >>> from piighost.models import Detection, Entity, Span
        >>> factory = FakerPlaceholderFactory(seed=42)
        >>> e = Entity(detections=(Detection(text="Patrick", label="PERSON", position=Span(0, 7), confidence=0.9),))
        >>> token = factory.create([e])[e]
        >>> isinstance(token, str) and len(token) > 0
        True
    """

    _faker: Faker
    _strategies: dict[str, FakerFn]

    @classmethod
    def from_config(cls, cfg: "FakerPlaceholderConfig") -> "FakerPlaceholderFactory":
        """Build a ``FakerPlaceholderFactory`` from its validated configuration."""
        return cls(faker=Faker(cfg.locale))

    def __init__(
        self,
        faker: Faker | None = None,
        strategies: dict[str, FakerFn] | None = None,
        seed: int | None = None,
    ) -> None:
        self._faker = faker or Faker()
        self._seed = seed

        if strategies is None:
            self._strategies = dict(DEFAULT_STRATEGIES)
        else:
            self._strategies = {k.lower(): v for k, v in strategies.items()}

    def create(self, entities: list[Entity]) -> dict[Entity, str]:
        """Create fake replacement tokens for all entities.

        Each entity is mapped to a fake value via its label. Entities
        sharing the same canonical text and label get the same fake value.

        Args:
            entities: The entities to create tokens for.

        Returns:
            A dict mapping each entity to a realistic fake value.
        """
        cache: dict[tuple[str, str], str] = {}
        result: dict[Entity, str] = {}

        for entity in entities:
            canonical = entity.canonical
            label_lower = entity.label.lower()
            key = (canonical, label_lower)

            if key not in cache:
                cache[key] = self._fake(canonical, label_lower)

            result[entity] = cache[key]

        return result

    def _seed_for(self, canonical: str, label_lower: str) -> int:
        """Derive a stable 64-bit seed from the entity identity.

        Folds the optional instance ``seed`` so two factories with
        different seeds diverge while each stays deterministic.
        """
        raw = f"{canonical}:{label_lower}"
        if self._seed is not None:
            raw = f"{raw}:{self._seed}"
        # crc32 is a deterministic (cross-process) 32-bit int, unlike the
        # PYTHONHASHSEED-salted builtin hash(). Good enough to spread seeds.
        return zlib.crc32(raw.encode())

    def _fake(self, canonical: str, label_lower: str) -> str:
        strategy = self._strategies.get(label_lower)
        if strategy is None:
            return f"<{label_lower.upper()}>"
        # Seed per entity so the same (text, label) always yields the same
        # value, independent of call order or RNG state.
        self._faker.seed_instance(self._seed_for(canonical, label_lower))
        return strategy(self._faker)
