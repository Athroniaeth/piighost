"""In-memory conversation memory, a process-local per-thread message cache."""

from collections import defaultdict

from piighost.conversation_memory.base import Forgotten, MessageRole
from piighost.models import Detection


class InMemoryConversationMemory:
    """Hold each thread's message-to-detections cache in a process-local dict.

    Suits development, tests, and single-process use. Nothing survives a restart
    and nothing is shared across processes, so a persistent backend is needed
    for multi-worker deployments. Detections are copied in and out so a caller
    cannot mutate the stored state through a reference it kept or received. Each
    message also carries the role of its author, so a value's first occurrence
    dates its provenance.
    """

    def __init__(self) -> None:
        """Start with no threads remembered."""
        self._threads: defaultdict[
            str, dict[str, tuple[MessageRole, list[Detection]]]
        ] = defaultdict(dict)

    async def remember(
        self,
        thread_id: str,
        message: str,
        detections: list[Detection],
        role: MessageRole = MessageRole.USER,
    ) -> None:
        """Cache the detections found in a message, replacing any prior entry."""
        self._threads[thread_id][message] = (role, list(detections))

    async def get_detections(
        self,
        thread_id: str,
        message: str | None = None,
    ) -> list[Detection] | None:
        """Return a thread's detections, for one message or the whole thread."""
        thread = self._threads[thread_id]

        if message is None:
            return [detection for _, cached in thread.values() for detection in cached]

        if message not in thread:
            return None

        return list(thread[message][1])

    async def get_provenance(self, thread_id: str) -> dict[str, MessageRole]:
        """Return the first-occurrence role of every value in the thread."""
        provenance: dict[str, MessageRole] = {}

        for role, cached in self._threads[thread_id].values():
            for detection in cached:
                provenance.setdefault(detection.text.casefold(), role)

        return provenance

    async def forget(self, thread_id: str) -> Forgotten:
        """Erase a thread and report how many messages and detections dropped."""
        thread = self._threads.pop(thread_id, {})
        detections = sum(len(cached) for _, cached in thread.values())
        return Forgotten(messages=len(thread), detections=detections)
