"""Conversation memory abstractions: the repository port and its erase result.

A conversation memory is the repository that persists, per thread, the
detections found in each message of a dialogue, from both user and model turns.
Caching by message lets an identical message resent later reuse its detections
instead of running detection again; the union of every message's detections
feeds the derivation of entities and their tokens. It stores detections only;
deriving entities is a service above the port, not the store's job.

There is no Base template here, unlike the pipeline stages. Backends differ by
their whole storage mechanism, an in-memory dict, a Redis client, a SQL table,
not by a single hook over one input, so there is no shared skeleton to template.
This is the pairwise exception to the always-template rule, the same reason the
fuzzy entity resolver stands apart from the linker.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from piighost.models import Detection


@dataclass(frozen=True, slots=True)
class Forgotten:
    """What forgetting a thread erased, as evidence for the right to erasure.

    Attributes:
        messages: How many cached messages were dropped.
        detections: How many detections across those messages were dropped.
    """

    messages: int
    detections: int


@runtime_checkable
class AnyConversationMemory(Protocol):
    """A repository of the detections found in each message of a thread.

    It caches, per thread, the detections of every message, from both user and
    model turns, keeps threads isolated, and can forget a thread wholesale for
    the right to erasure.
    """

    async def remember(
        self,
        thread_id: str,
        message: str,
        detections: list[Detection],
    ) -> None:
        """Cache the detections found in a message, replacing any prior entry.

        Args:
            thread_id: The conversation the message belongs to.
            message: The message the detections were found in, the cache key.
            detections: The detections found in the message, possibly empty.
        """
        ...

    async def get_detections(
        self,
        thread_id: str,
        message: str | None = None,
    ) -> list[Detection] | None:
        """Return a thread's detections, for one message or the whole thread.

        With no message, or None, it returns the union of every message's
        detections in first-seen order, which is always a list. With a message,
        it returns that message's cached detections: an empty list means the
        message was seen and held no PII, so detection can be skipped, while None
        means the message was never seen, so detection must run.

        Args:
            thread_id: The conversation to read.
            message: The message to look up, or None for the whole thread.

        Returns:
            The union as a list when no message is given, otherwise the
            message's cached detections, an empty list, or None on a miss.
        """
        ...

    async def forget(self, thread_id: str) -> Forgotten:
        """Erase a thread and report how much was dropped.

        Args:
            thread_id: The conversation to erase. Forgetting an unknown thread
                drops nothing and reports zero.

        Returns:
            How many messages and detections were erased.
        """
        ...
