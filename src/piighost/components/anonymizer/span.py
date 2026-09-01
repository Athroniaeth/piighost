"""Span-replacement anonymizer built on a placeholder factory."""

from collections.abc import Mapping

from piighost.components.anonymizer.base import BaseAnonymizer, PreservationT
from piighost.exceptions import OverlappingSpansError
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
        """Return text with each entity's spans replaced by its given token.

        Raises:
            OverlappingSpansError: If two spans overlap. The one-pass rewrite
                assumes disjoint spans, which the overlap-resolver stage
                guarantees, so an overlap here fails closed rather than splice a
                clear fragment of one detection into another.
        """
        edits = sorted(
            (span, tokens[entity]) for entity in entities for span in entity.spans
        )
        cursor = 0
        pieces: list[str] = []

        for span, token in edits:
            if span.start < cursor:
                raise OverlappingSpansError(
                    f"Overlapping spans at offset {span.start} (previous edit ended "
                    f"at {cursor}); the overlap-resolver stage must run first."
                )
            pieces.append(text[cursor : span.start])
            pieces.append(token)
            cursor = span.end

        pieces.append(text[cursor:])
        return "".join(pieces)
