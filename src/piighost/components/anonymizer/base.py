"""Anonymizer abstractions: the port and its span-replacement result."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Generic, Protocol, runtime_checkable

from typing_extensions import TypeVar

from piighost.models import Entity
from piighost.components.placeholder.tags import PlaceholderPreservation

PreservationT_co = TypeVar(
    "PreservationT_co",
    bound=PlaceholderPreservation,
    default=PlaceholderPreservation,
    covariant=True,
)


@dataclass(frozen=True, slots=True)
class Anonymization(Generic[PreservationT_co]):
    """The outcome of anonymizing a text: the rewritten text and its tokens.

    Attributes:
        text: The text with every entity occurrence replaced by its token.
        tokens: The token each entity was replaced with, typed by what the
            factory preserves, so a caller can reverse the mapping when the
            tokens preserve identity.
    """

    text: str
    tokens: Mapping[Entity, PreservationT_co]


@runtime_checkable
class AnyAnonymizer(Protocol[PreservationT_co]):
    """A component that replaces each entity's spans with its placeholder token.

    Generic on what the tokens preserve, so a consumer such as the middleware can
    require an anonymizer whose tokens preserve identity and reject one whose
    tokens do not, at type-check time.
    """

    def anonymize(
        self,
        text: str,
        entities: list[Entity],
    ) -> Anonymization[PreservationT_co]:
        """Return the anonymized text and the token used for each entity.

        Args:
            text: The original text the entities were found in.
            entities: The entities to replace, their spans non-overlapping.

        Returns:
            The anonymized text and the entity-to-token mapping.
        """
        ...

    def create(self, entities: list[Entity]) -> Mapping[Entity, PreservationT_co]:
        """Return the token each entity is replaced with, without touching text.

        Splitting token assignment out of rendering lets a caller assign tokens
        over one entity set, such as a whole conversation, then render several
        texts against those same tokens.

        Args:
            entities: The entities to assign tokens to.

        Returns:
            The token each entity maps to.
        """
        ...

    def render(
        self,
        text: str,
        entities: list[Entity],
        tokens: Mapping[Entity, str],
    ) -> str:
        """Return text with each entity's spans replaced by its given token.

        Args:
            text: The text to render.
            entities: The entities whose spans to replace, non-overlapping.
            tokens: The token to use for each entity.

        Returns:
            The text with the entities' spans replaced.
        """
        ...

    def deanonymize(self, text: str, tokens: Mapping[Entity, str]) -> str:
        """Return the text with every known token replaced by its entity value.

        The mapping is the entity-to-token one an anonymization produced, read
        in reverse. Any text carrying those tokens can be restored, including a
        text the pipeline never produced, such as a fresh model reply. Tokens
        absent from the mapping are left untouched. Restoration is only
        unambiguous when the tokens preserve identity, since two entities that
        share a token collapse to one value.

        Args:
            text: The text whose tokens should be restored.
            tokens: The entity-to-token mapping from the anonymization.

        Returns:
            The text with each known token replaced by its entity's value.
        """
        ...
