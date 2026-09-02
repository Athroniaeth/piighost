"""Anonymizer abstractions: the port and its span-replacement result."""

import re
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Generic, Protocol, runtime_checkable

from typing_extensions import TypeVar

from piighost.components.placeholder.base import AnyPlaceholderFactory
from piighost.components.placeholder.tags import PlaceholderPreservation
from piighost.models import Entity

PreservationT_co = TypeVar(
    "PreservationT_co",
    bound=PlaceholderPreservation,
    default=PlaceholderPreservation,
    covariant=True,
)
"""What the anonymizer's tokens preserve, on the port and its result.

Covariant, since an anonymizer only returns tokens, so one whose tokens preserve
more satisfies a consumer asking for less.
"""

PreservationT = TypeVar(
    "PreservationT",
    bound=PlaceholderPreservation,
    default=PlaceholderPreservation,
)
"""Invariant tag for the template and its adapters.

The AnyAnonymizer port is covariant, since it only returns tokens; the template
below both takes a factory of this tag and returns tokens of it, so it needs the
invariant variable rather than the covariant PreservationT_co.
"""


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

    @property
    def factory(self) -> AnyPlaceholderFactory[PreservationT_co]:
        """The placeholder factory that assigns tokens to entities.

        A read-only property rather than a mutable attribute, so the covariant
        preservation tag stays in a covariant position and the protocol is
        variance sound.
        """
        ...

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


class BaseAnonymizer(ABC, Generic[PreservationT]):
    """Assign tokens through a factory and compose them into anonymized text.

    The skeleton lives here: ask the placeholder factory for one token per
    entity, render the text against those tokens, and pair the two into an
    Anonymization; deanonymize reverses the mapping. A subclass defines render,
    the only step that varies, the rule that rewrites the text given the
    entities and their tokens.

    Attributes:
        factory: The placeholder factory that names each entity.
    """

    def __init__(self, ph_factory: AnyPlaceholderFactory[PreservationT]) -> None:
        """Store the placeholder factory that assigns a token to each entity."""
        self.factory = ph_factory

    def create(self, entities: list[Entity]) -> Mapping[Entity, PreservationT]:
        """Return the token the factory assigns to each entity."""
        return self.factory.create(entities)

    def anonymize(
        self,
        text: str,
        entities: list[Entity],
    ) -> Anonymization[PreservationT]:
        """Return the anonymized text and the token used for each entity."""
        tokens = self.create(entities)
        rendered = self.render(text, entities, tokens)
        return Anonymization(text=rendered, tokens=tokens)

    def deanonymize(self, text: str, tokens: Mapping[Entity, str]) -> str:
        """Return the text with every known token replaced by its entity value.

        The replacement is a single regex pass over an alternation of the tokens,
        longest first. Longest-first avoids a token that prefixes another (for
        example [PERSON:1 and [PERSON:10 with an empty suffix) restoring the
        shorter one inside the longer, and a single pass never rescans a value it
        just spliced in, so a restored value that itself looks like a token is
        left untouched.
        """
        values = {token: entity.text for entity, token in tokens.items()}
        if not values:
            return text

        alternation = "|".join(
            re.escape(token) for token in sorted(values, key=len, reverse=True)
        )
        pattern = re.compile(alternation)
        return pattern.sub(lambda match: values[match.group(0)], text)

    @abstractmethod
    def render(
        self,
        text: str,
        entities: list[Entity],
        tokens: Mapping[Entity, str],
    ) -> str:
        """Return text with each entity's spans replaced by its given token."""
        ...
