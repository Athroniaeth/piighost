"""Placeholder factory port: the contract for turning entities into tokens."""

import re
from abc import abstractmethod
from collections import defaultdict
from collections.abc import Awaitable, Callable, Mapping
from typing import Protocol, runtime_checkable

from typing_extensions import TypeVar

from piighost.components.placeholder.streaming import (
    DEFAULT_PREFIX,
    DEFAULT_SUFFIX,
    AsyncPlaceholderStreamDecoder,
    PlaceholderStreamDecoder,
    compile_token_pattern,
)
from piighost.components.placeholder.tags import (
    PlaceholderPreservation,
    PreservesLabeledIdentityOpaque,
)
from piighost.models import Entity

PreservationT_co = TypeVar(
    "PreservationT_co",
    bound=PlaceholderPreservation,
    default=PlaceholderPreservation,
    covariant=True,
)
"""Phantom tag stating how much information a factory's tokens preserve.

Defaults to PlaceholderPreservation so a bare AnyPlaceholderFactory annotation
still type-checks. Covariant, so a factory tagged with a more specific
preservation satisfies a consumer asking for a looser one.
"""


@runtime_checkable
class AnyPlaceholderFactory(Protocol[PreservationT_co]):
    """A component that turns entities into their replacement tokens.

    The phantom type parameter declares what the tokens preserve, per the tags
    module, letting a consumer such as the middleware reject an incompatible
    factory at type-check time, for instance a label-only factory where a unique
    identity is required.
    """

    def create(self, entities: list[Entity]) -> Mapping[Entity, PreservationT_co]:
        """Return a replacement token for each entity.

        Each token is an instance of the factory's preservation tag, so its type
        states what it preserves. The return is a Mapping rather than a dict
        because the tag parameter is covariant, which a dict value could not be.

        Must be deterministic: the same entities yield the same tokens on every
        call, because the pipeline calls it more than once per run, once to
        render the anonymized text and once to collect the tokens handed to the
        guard rail. A factory that drifts between calls desynchronizes the two.

        Args:
            entities: The entities to build tokens for.

        Returns:
            A mapping from each entity to its token.
        """
        ...


class BaseDelimitedPlaceholderFactory:
    """Template for factories whose tokens wrap an inner form in delimiters.

    A delimited factory renders each token as prefix + inner + suffix, such as
    <<PERSON>> or <<PERSON:1>>, where the subclass decides the inner form. The
    delimiters default to << and >> but are configurable, so tokens can be shaped
    to what a downstream model or parser recognizes and later found again. Only
    the delimiters live here; the inner form and the preservation tag belong to
    the subclass, so this class is a mixin, incomplete on its own.

    Attributes:
        prefix: The opening delimiter wrapped around every token.
        suffix: The closing delimiter wrapped around every token.
    """

    def __init__(
        self, prefix: str = DEFAULT_PREFIX, suffix: str = DEFAULT_SUFFIX
    ) -> None:
        """Store the opening and closing delimiters wrapped around every token."""
        self.prefix = prefix
        self.suffix = suffix

    def _wrap(self, inner: str) -> str:
        """Return the inner form wrapped in the configured delimiters."""
        return f"{self.prefix}{inner}{self.suffix}"

    @property
    def token_pattern(self) -> re.Pattern[str]:
        """A regex matching this factory's tokens, capturing the inner form.

        It follows the current delimiters, so a factory built with custom ones
        finds exactly the tokens it emits.
        """
        return compile_token_pattern(self.prefix, self.suffix)

    def find_tokens(self, text: str) -> list[str]:
        """Return every placeholder token occurring in the text, in order."""
        return [match.group() for match in self.token_pattern.finditer(text)]

    def stream_decoder(self, replace: Callable[[str], str]) -> PlaceholderStreamDecoder:
        """Return a decoder that rewrites this factory's tokens over a stream.

        The decoder keeps tokens whole across streamed fragments and rewrites
        each with replace, a plain callback for a synchronous stream.
        """
        return PlaceholderStreamDecoder(replace, self.prefix, self.suffix)

    def async_stream_decoder(
        self, replace: Callable[[str], Awaitable[str]]
    ) -> AsyncPlaceholderStreamDecoder:
        """Return an async decoder that rewrites this factory's tokens over a stream.

        The async twin of stream_decoder: it keeps tokens whole across streamed
        fragments and awaits replace for each completed token, so a coroutine
        deanonymization, local or remote, can drive streaming restoration.
        """
        return AsyncPlaceholderStreamDecoder(replace, self.prefix, self.suffix)


class BaseCounterPlaceholderFactory(
    BaseDelimitedPlaceholderFactory,
    AnyPlaceholderFactory[PreservesLabeledIdentityOpaque],
):
    """Number each entity within its label, rendering the count through a hook.

    The skeleton lives here: number the entities per label in order, so the
    first person becomes ordinal 1, the second 2, while an email starts its own
    count at 1, then hand each label and its ordinal to the subclass to render
    into a token. A subclass defines _token, the only step that varies, whether
    the ordinal shows as a plain number or an opaque hash. Every entity gets a
    distinct token, hence the shared tag PreservesLabeledIdentityOpaque.
    """

    def create(
        self, entities: list[Entity]
    ) -> dict[Entity, PreservesLabeledIdentityOpaque]:
        """Return a per-label numbered token for every entity, in order."""
        counters: dict[str, int] = defaultdict(int)
        tokens: dict[Entity, PreservesLabeledIdentityOpaque] = {}

        for entity in entities:
            counters[entity.label] += 1
            tokens[entity] = self._token(entity.label, counters[entity.label])

        return tokens

    @abstractmethod
    def _token(self, label: str, number: int) -> PreservesLabeledIdentityOpaque:
        """Render one label and its per-label ordinal as a token."""
        ...
