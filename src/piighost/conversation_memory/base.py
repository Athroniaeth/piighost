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

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from piighost.models import Detection


class MessageRole(Enum):
    """Who authored a message, used to date a value's first occurrence.

    USER for a message from the person, ASSISTANT for one from the model. A
    value's provenance is the role of its earliest occurrence in the thread, so
    a value the assistant introduced can be left in clear.
    """

    USER = "user"
    ASSISTANT = "assistant"


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
        role: MessageRole = MessageRole.USER,
    ) -> None:
        """Cache the detections found in a message, replacing any prior entry.

        Args:
            thread_id: The conversation the message belongs to.
            message: The message the detections were found in, the cache key.
            detections: The detections found in the message, possibly empty.
            role: Who authored the message, dating the values it introduces.
        """
        ...

    async def get_provenance(self, thread_id: str) -> Mapping[str, MessageRole]:
        """Return, per value, the role of its first occurrence in the thread.

        The value is the detection text, casefolded, so case variants share one
        entry. The role is that of the earliest message holding the value, in
        first-seen order, so a value the assistant introduced reads as ASSISTANT
        even if a later user message repeats it.

        Args:
            thread_id: The conversation to read.

        Returns:
            A mapping from each casefolded value to its first-occurrence role,
            empty for a thread never written to.
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
