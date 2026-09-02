"""In-memory conversation memory, a process-local per-thread message cache."""

import time
from collections import OrderedDict
from collections.abc import Callable

from piighost.conversation_memory.base import Forgotten, MessageRole
from piighost.models import Detection

_Thread = dict[str, tuple[MessageRole, list[Detection]]]


class InMemoryConversationMemory:
    """Hold each thread's message-to-detections cache in a process-local dict.

    Suits development, tests, and single-process use. Nothing survives a restart
    and nothing is shared across processes, so a persistent backend is needed for
    multi-worker deployments. Detections are copied in and out so a caller cannot
    mutate the stored state through a reference it kept or received. Each message
    also carries the role of its author, so a value's first occurrence dates its
    provenance.

    Growth is bounded when configured. max_threads evicts the least recently used
    thread once the count exceeds it, and ttl expires a thread that has not been
    written for that many seconds, lazily on the next access. Left unset, the
    store grows until forget_thread is called, so bound it or forget threads in a
    long-lived process.
    """

    def __init__(
        self,
        max_threads: int | None = None,
        ttl: float | None = None,
        time_source: Callable[[], float] = time.monotonic,
    ) -> None:
        """Start with no threads, under the given bounding and clock.

        max_threads caps how many threads are kept, evicting the least recently
        used beyond it. ttl expires a thread that many seconds after its last
        write, dropped on the next access. time_source is the clock ttl reads,
        injectable for tests.
        """
        self._threads: OrderedDict[str, _Thread] = OrderedDict()
        self._expiry: dict[str, float] = {}
        self._max_threads = max_threads
        self._ttl = ttl
        self._now = time_source

    async def remember(
        self,
        thread_id: str,
        message: str,
        detections: list[Detection],
        role: MessageRole = MessageRole.USER,
    ) -> None:
        """Cache the detections found in a message, replacing any prior entry."""
        if self._expired(thread_id):
            self._drop(thread_id)

        thread = self._threads.get(thread_id)
        if thread is None:
            thread = {}
            self._threads[thread_id] = thread

        thread[message] = (role, list(detections))
        self._threads.move_to_end(thread_id)
        if self._ttl is not None:
            self._expiry[thread_id] = self._now() + self._ttl
        self._evict()

    async def get_detections(
        self,
        thread_id: str,
        message: str | None = None,
    ) -> list[Detection] | None:
        """Return a thread's detections, for one message or the whole thread."""
        thread = self._live_thread(thread_id)

        if thread is None:
            return [] if message is None else None

        if message is None:
            return [detection for _, cached in thread.values() for detection in cached]

        if message not in thread:
            return None

        return list(thread[message][1])

    async def get_provenance(self, thread_id: str) -> dict[str, MessageRole]:
        """Return the first-occurrence role of every value in the thread."""
        provenance: dict[str, MessageRole] = {}
        thread = self._live_thread(thread_id)
        if thread is None:
            return provenance

        for role, cached in thread.values():
            for detection in cached:
                provenance.setdefault(detection.text.casefold(), role)

        return provenance

    async def forget(self, thread_id: str) -> Forgotten:
        """Erase a thread and report how many messages and detections dropped."""
        thread = self._threads.pop(thread_id, {})
        self._expiry.pop(thread_id, None)
        detections = sum(len(cached) for _, cached in thread.values())
        return Forgotten(messages=len(thread), detections=detections)

    def _live_thread(self, thread_id: str) -> _Thread | None:
        """Return the thread if present and unexpired, else None, without creating one.

        Reading through this never inserts a phantom entry, so a read of an
        unknown thread cannot evict a real one. A present but expired thread is
        dropped and read as absent. A live thread is marked most recently used.
        """
        if thread_id not in self._threads:
            return None
        if self._expired(thread_id):
            self._drop(thread_id)
            return None
        self._threads.move_to_end(thread_id)
        return self._threads[thread_id]

    def _expired(self, thread_id: str) -> bool:
        """Whether the thread has a ttl deadline that has now passed."""
        deadline = self._expiry.get(thread_id)
        return deadline is not None and self._now() >= deadline

    def _drop(self, thread_id: str) -> None:
        """Remove a thread and its expiry deadline."""
        self._threads.pop(thread_id, None)
        self._expiry.pop(thread_id, None)

    def _evict(self) -> None:
        """Evict least recently used threads while over the max_threads bound."""
        if self._max_threads is None:
            return
        while len(self._threads) > self._max_threads:
            oldest, _ = self._threads.popitem(last=False)
            self._expiry.pop(oldest, None)
