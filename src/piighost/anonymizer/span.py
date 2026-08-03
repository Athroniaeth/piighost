"""Span-replacement anonymizer built on a placeholder factory."""

from collections.abc import Mapping
from typing import Generic

from typing_extensions import TypeVar

from piighost.anonymizer.base import Anonymization
from piighost.models import Entity
from piighost.placeholder.base import AnyPlaceholderFactory
from piighost.placeholder.tags import PlaceholderPreservation

PreservationT = TypeVar(
    "PreservationT",
    bound=PlaceholderPreservation,
    default=PlaceholderPreservation,
)


class Anonymizer(Generic[PreservationT]):
    """Replace each entity's spans with the token a factory assigns it.

    It asks the factory for one token per entity, then rewrites the text so every
    occurrence of an entity becomes its token. The spans are edited left to right
    over one pass, which stays correct because upstream stages leave them
    non-overlapping, so no edit shifts an offset another edit still needs.

    Attributes:
        factory: The placeholder factory that names each entity.
    """

    def __init__(self, ph_factory: AnyPlaceholderFactory[PreservationT]) -> None:
        """Store the placeholder factory that assigns a token to each entity."""
        self.factory = ph_factory

    def create(self, entities: list[Entity]) -> Mapping[Entity, PreservationT]:
        """Return the token the factory assigns to each entity."""
        return self.factory.create(entities)

    def render(
        self,
        text: str,
        entities: list[Entity],
        tokens: Mapping[Entity, str],
    ) -> str:
        """Return text with each entity's spans replaced by its given token."""
        cursor = 0
        pieces: list[str] = []

        edits = sorted(
            (span, tokens[entity]) for entity in entities for span in entity.spans
        )

        for span, token in edits:
            pieces.append(text[cursor : span.start])
            pieces.append(token)
            cursor = span.end

        pieces.append(text[cursor:])
        return "".join(pieces)

    def anonymize(
        self,
        text: str,
        entities: list[Entity],
    ) -> Anonymization[PreservationT]:
        """Return the anonymized text and the token used for each entity."""
        tokens = self.create(entities)
        return Anonymization(text=self.render(text, entities, tokens), tokens=tokens)

    def deanonymize(self, text: str, tokens: Mapping[Entity, str]) -> str:
        """Return the text with every known token replaced by its entity value."""
        values = {token: entity.text for entity, token in tokens.items()}

        for token, value in values.items():
            text = text.replace(token, value)

        return text
