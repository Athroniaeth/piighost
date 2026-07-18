"""Placeholder factory port: the contract for turning entities into tokens."""

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from typing_extensions import TypeVar

from piighost.models import Entity
from piighost.placeholder.tags import PlaceholderPreservation

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
