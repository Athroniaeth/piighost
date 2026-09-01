"""Span-replacement anonymizer built on a placeholder factory."""

from collections.abc import Mapping

from piighost.components.anonymizer.base import BaseAnonymizer, PreservationT
from piighost.components.placeholder.base import (
    AnyPlaceholderFactory,
    BaseDelimitedPlaceholderFactory,
)
from piighost.exceptions import OverlappingSpansError
from piighost.models import Entity

_ZERO_WIDTH_SPACE = "\u200b"
"""Invisible character spliced into a user-typed token to break its grammar."""


class Anonymizer(BaseAnonymizer[PreservationT]):
    """Replace each entity's spans with the token a factory assigns it.

    It rewrites the text so every occurrence of an entity becomes its token. The
    spans are edited left to right over one pass, which stays correct because
    upstream stages leave them non-overlapping, so no edit shifts an offset
    another edit still needs.
    """

    def __init__(
        self,
        ph_factory: AnyPlaceholderFactory[PreservationT],
        escape_existing_tokens: bool = True,
    ) -> None:
        """Store the factory and whether to neutralize user-typed tokens.

        escape_existing_tokens defaults to True so a token a user typed in the
        input, such as <<PERSON:2>>, is broken before it can masquerade as one
        the factory issued and hijack another entity's value at restoration. It
        only applies when the factory emits a recognizable delimited grammar.
        Pass False to leave the input verbatim.
        """
        super().__init__(ph_factory)
        self._escape_existing_tokens = escape_existing_tokens

    def render(
        self,
        text: str,
        entities: list[Entity],
        tokens: Mapping[Entity, str],
    ) -> str:
        """Return text with each entity's spans replaced by its given token.

        Only the literal runs between entity spans are neutralized, never the
        tokens spliced in, and offsets are untouched, so the entity spans still
        line up.

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
            pieces.append(self._neutralize(text[cursor : span.start]))
            pieces.append(token)
            cursor = span.end

        pieces.append(self._neutralize(text[cursor:]))
        return "".join(pieces)

    def _neutralize(self, run: str) -> str:
        """Break any token the user typed in a literal run of the input.

        A zero-width space is spliced after the first character of each match, so
        the delimiters no longer line up and the run cannot be restored as a real
        token. Left untouched when escaping is off or the factory has no
        recognizable grammar.
        """
        factory = self.factory
        if not self._escape_existing_tokens or not isinstance(
            factory, BaseDelimitedPlaceholderFactory
        ):
            return run
        return factory.token_pattern.sub(
            lambda match: match.group()[0] + _ZERO_WIDTH_SPACE + match.group()[1:],
            run,
        )
