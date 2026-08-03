"""Span-replacement anonymizer built on a placeholder factory."""

from collections.abc import Mapping

from piighost.components.anonymizer.base import BaseAnonymizer, PreservationT
from piighost.models import Entity


class Anonymizer(BaseAnonymizer[PreservationT]):
    """Replace each entity's spans with the token a factory assigns it.

    It rewrites the text so every occurrence of an entity becomes its token. The
    spans are edited left to right over one pass, which stays correct because
    upstream stages leave them non-overlapping, so no edit shifts an offset
    another edit still needs.
    """

    def render(
        self,
        text: str,
        entities: list[Entity],
        tokens: Mapping[Entity, str],
    ) -> str:
        """Return text with each entity's spans replaced by its given token."""
        edits = sorted(
            (span, tokens[entity]) for entity in entities for span in entity.spans
        )
        cursor = 0
        pieces: list[str] = []

        for span, token in edits:
            pieces.append(text[cursor : span.start])
            pieces.append(token)
            cursor = span.end

        pieces.append(text[cursor:])
        return "".join(pieces)
