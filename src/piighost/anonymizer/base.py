"""Anonymizer abstractions: the port and its span-replacement result."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Generic, Protocol, runtime_checkable

from typing_extensions import TypeVar

from piighost.models import Entity
from piighost.placeholder.tags import PlaceholderPreservation

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
        self, text: str, entities: list[Entity],
    ) -> Anonymization[PreservationT_co]:
        """Return the anonymized text and the token used for each entity.

        Args:
            text: The original text the entities were found in.
            entities: The entities to replace, their spans non-overlapping.

        Returns:
            The anonymized text and the entity-to-token mapping.
        """
        ...
