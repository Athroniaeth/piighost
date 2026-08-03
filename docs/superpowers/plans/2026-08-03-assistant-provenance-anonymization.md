# Provenance-Aware Anonymization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Do not anonymize a value whose first occurrence in a thread comes from an assistant message, so the model keeps its world knowledge of entities it introduced.

**Architecture:** Provenance (the role of a value's first occurrence) is recorded in the ConversationMemory, keyed by casefolded value in first-seen order. The ThreadAnonymizationPipeline gains a `role` argument, excludes assistant-provenance entities from token assignment, and exempts the preserved values from the guard. An `AssistantEntityStrategy` (PRESERVE/ANONYMIZE/IGNORE) on the LangChain middleware maps each message's role and drives the behavior.

**Tech Stack:** Python 3.11+, pytest (asyncio_mode=auto), ruff, pyrefly, bandit, uv. LangChain optional extra for the middleware, fakeredis + cryptography for the Redis backend tests.

**Conventions:** Run tooling with `uv run --no-sync`. Clear `__pycache__` before pytest: `find src tests -name __pycache__ -type d -exec rm -rf {} +`. Code artifacts (docstrings, comments, identifiers) in English. Tests are data-driven where sensible and each test carries a one-line docstring. Reference spec: `docs/superpowers/specs/2026-08-03-assistant-provenance-anonymization-design.md`.

**Definitions used across tasks (must stay identical):**
- `MessageRole` enum: `USER = "user"`, `ASSISTANT = "assistant"`.
- Provenance key = `detection.text.casefold()`.
- `AssistantEntityStrategy` enum: `PRESERVE = "preserve"`, `ANONYMIZE = "anonymize"`, `IGNORE = "ignore"`.
- Memory port methods: `remember(thread_id, message, detections, role=MessageRole.USER)`, `get_provenance(thread_id) -> Mapping[str, MessageRole]`.
- Pipeline: `anonymize(text, thread_id, role=MessageRole.USER)`.

---

## File Structure

- `src/piighost/conversation_memory/base.py` — add `MessageRole`; add `role` param to `remember` and `get_provenance` to the `AnyConversationMemory` port.
- `src/piighost/conversation_memory/memory.py` — `InMemoryConversationMemory` stores `(role, detections)` per message and implements `get_provenance`.
- `src/piighost/conversation_memory/redis_backend.py` — Redis stores the role in the encrypted blob and implements `get_provenance`.
- `src/piighost/conversation_memory/__init__.py` — export `MessageRole`.
- `src/piighost/pipeline/thread.py` — `anonymize`/`_detect` take `role`; `_thread_tokens` drops assistant-provenance entities; guard receives preserved values.
- `src/piighost/pipeline/base.py` — `_guard` takes an `expected` set of values to exempt.
- `src/piighost/integrations/middleware/strategy.py` — add `AssistantEntityStrategy`.
- `src/piighost/integrations/middleware/langchain.py` — `assistant_strategy`, role mapping, `_rewrite` passes the message.
- `src/piighost/integrations/middleware/__init__.py` — export `AssistantEntityStrategy`.
- `tests/conversation_memory/test_in_memory.py`, `tests/conversation_memory/test_redis.py`, `tests/pipeline/test_thread.py`, `tests/integrations/middleware/test_middleware.py` — new test classes.
- `tests/regression/test_imports.py` — `PUBLIC_API` entries.
- `examples/langchain_assistant_provenance.py` — the Napoléon scenario over the three strategies.
- `design/rewrite-blueprint.md` — decision-journal entry.

---

## Task 1: MessageRole enum and memory port

**Files:**
- Modify: `src/piighost/conversation_memory/base.py`
- Modify: `src/piighost/conversation_memory/__init__.py`
- Modify: `tests/regression/test_imports.py`

- [ ] **Step 1: Add the PUBLIC_API regression entry (failing test)**

In `tests/regression/test_imports.py`, add to the `PUBLIC_API` list, next to the other conversation_memory entries:

```python
    ("piighost.conversation_memory", "MessageRole"),
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --no-sync pytest tests/regression/test_imports.py -q`
Expected: FAIL, the parametrized case for `MessageRole` fails on `hasattr`.

- [ ] **Step 3: Add MessageRole and extend the port**

In `src/piighost/conversation_memory/base.py`, update the imports at the top:

```python
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from piighost.models import Detection
```

Add the enum after the imports, before `Forgotten`:

```python
class MessageRole(Enum):
    """Who authored a message, used to date a value's first occurrence.

    USER for a message from the person, ASSISTANT for one from the model. A
    value's provenance is the role of its earliest occurrence in the thread, so
    a value the assistant introduced can be left in clear.
    """

    USER = "user"
    ASSISTANT = "assistant"
```

In the `AnyConversationMemory` Protocol, change `remember` to take a role and add `get_provenance`:

```python
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
```

In `src/piighost/conversation_memory/__init__.py`, add `MessageRole` to the imports and `__all__`:

```python
from piighost.conversation_memory.base import (
    AnyConversationMemory,
    Forgotten,
    MessageRole,
)
```

Add `"MessageRole"` to the `__all__` list (keep it alphabetically sorted).

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --no-sync pytest tests/regression/test_imports.py -q`
Expected: PASS.

- [ ] **Step 5: Lint and typecheck**

Run: `uv run --no-sync ruff format src/piighost/conversation_memory tests/regression/test_imports.py -q && uv run --no-sync ruff check src/piighost/conversation_memory && uv run --no-sync pyrefly check src/piighost/conversation_memory`
Expected: All checks passed, 0 errors.

Note: `InMemoryConversationMemory` and `RedisConversationMemory` do not yet implement `get_provenance`. The `@runtime_checkable` `isinstance` check tests only method names present at runtime, and `get_provenance` is not yet defined on them, so run only the import test now; the memory tests come in Tasks 2 and 3.

- [ ] **Step 6: Commit**

```bash
git add src/piighost/conversation_memory/base.py src/piighost/conversation_memory/__init__.py tests/regression/test_imports.py
git commit -m "feat(memory): add MessageRole and the provenance port"
```

---

## Task 2: In-memory provenance

**Files:**
- Modify: `src/piighost/conversation_memory/memory.py`
- Test: `tests/conversation_memory/test_in_memory.py`

- [ ] **Step 1: Write the failing tests**

Add to the top imports of `tests/conversation_memory/test_in_memory.py`:

```python
from piighost.conversation_memory import (
    AnyConversationMemory,
    Forgotten,
    InMemoryConversationMemory,
    MessageRole,
)
```

Add a new test class at the end of the file:

```python
class TestProvenance:
    async def test_records_the_role_of_a_first_occurrence(self) -> None:
        """A value's provenance is the role of the message that first held it."""
        memory = InMemoryConversationMemory()
        await memory.remember("t1", "a1", [_detection("Napoleon")], MessageRole.ASSISTANT)
        assert await memory.get_provenance("t1") == {"napoleon": MessageRole.ASSISTANT}

    async def test_first_occurrence_wins(self) -> None:
        """A later message with the same value does not change its provenance."""
        memory = InMemoryConversationMemory()
        await memory.remember("t1", "u1", [_detection("Napoleon")], MessageRole.USER)
        await memory.remember("t1", "a1", [_detection("Napoleon")], MessageRole.ASSISTANT)
        assert await memory.get_provenance("t1") == {"napoleon": MessageRole.USER}

    async def test_provenance_folds_case(self) -> None:
        """Case variants of a value share one provenance entry."""
        memory = InMemoryConversationMemory()
        await memory.remember("t1", "a1", [_detection("Napoleon")], MessageRole.ASSISTANT)
        await memory.remember("t1", "u1", [_detection("napoleon")], MessageRole.USER)
        assert await memory.get_provenance("t1") == {"napoleon": MessageRole.ASSISTANT}

    async def test_default_role_is_user(self) -> None:
        """Remembering without a role records USER provenance."""
        memory = InMemoryConversationMemory()
        await memory.remember("t1", "u1", [_detection("Emma")])
        assert await memory.get_provenance("t1") == {"emma": MessageRole.USER}

    async def test_unknown_thread_has_no_provenance(self) -> None:
        """A thread never written to yields an empty provenance map."""
        memory = InMemoryConversationMemory()
        assert await memory.get_provenance("never") == {}
```

- [ ] **Step 2: Run to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/conversation_memory/test_in_memory.py -q`
Expected: FAIL, `get_provenance` does not exist and `remember` rejects the role argument.

- [ ] **Step 3: Implement provenance in the in-memory backend**

Replace the whole body of `src/piighost/conversation_memory/memory.py`:

```python
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
            return [
                detection for _, cached in thread.values() for detection in cached
            ]

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
```

- [ ] **Step 4: Run to verify it passes**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/conversation_memory/test_in_memory.py -q`
Expected: PASS (existing tests plus the new provenance class).

- [ ] **Step 5: Lint and typecheck**

Run: `uv run --no-sync ruff format src/piighost/conversation_memory/memory.py tests/conversation_memory/test_in_memory.py -q && uv run --no-sync ruff check src/piighost/conversation_memory/memory.py && uv run --no-sync pyrefly check src/piighost/conversation_memory/memory.py`
Expected: All checks passed, 0 errors.

- [ ] **Step 6: Commit**

```bash
git add src/piighost/conversation_memory/memory.py tests/conversation_memory/test_in_memory.py
git commit -m "feat(memory): record provenance in the in-memory backend"
```

---

## Task 3: Redis provenance

**Files:**
- Modify: `src/piighost/conversation_memory/redis_backend.py`
- Test: `tests/conversation_memory/test_redis.py`

- [ ] **Step 1: Write the failing tests**

Add to the top imports of `tests/conversation_memory/test_redis.py`:

```python
from piighost.conversation_memory import Forgotten, MessageRole
```

Add a new test class at the end of the file:

```python
class TestProvenance:
    async def test_records_first_occurrence_role(self) -> None:
        """A value keeps the role of the message that first held it."""
        memory, _ = _make()
        await memory.remember("t1", "u1", [_detection("Napoleon")], MessageRole.USER)
        await memory.remember("t1", "a1", [_detection("Napoleon")], MessageRole.ASSISTANT)
        assert await memory.get_provenance("t1") == {"napoleon": MessageRole.USER}

    async def test_default_role_is_user(self) -> None:
        """Remembering without a role records USER provenance."""
        memory, _ = _make()
        await memory.remember("t1", "u1", [_detection("Emma")])
        assert await memory.get_provenance("t1") == {"emma": MessageRole.USER}

    async def test_unknown_thread_has_no_provenance(self) -> None:
        """A thread never written to yields an empty provenance map."""
        memory, _ = _make()
        assert await memory.get_provenance("never") == {}
```

- [ ] **Step 2: Run to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/conversation_memory/test_redis.py -q`
Expected: FAIL, `get_provenance` does not exist and `remember` rejects the role.

- [ ] **Step 3: Implement provenance in the Redis backend**

In `src/piighost/conversation_memory/redis_backend.py`, add `MessageRole` to the base import:

```python
from piighost.conversation_memory.base import Forgotten, MessageRole
```

Replace `_dumps` and `_loads` (the module-level helpers) with role-carrying versions:

```python
def _dumps(role: MessageRole, detections: list[Detection]) -> bytes:
    """Serialize a message's role and detections to JSON bytes for storage."""
    payload = {
        "role": role.value,
        "detections": [detection.to_dict() for detection in detections],
    }
    return json.dumps(payload).encode()


def _loads(data: bytes) -> tuple[MessageRole, list[Detection]]:
    """Rebuild a message's role and detections from the bytes written by _dumps."""
    payload = json.loads(data)
    role = MessageRole(payload["role"])
    detections = [Detection.from_dict(item) for item in payload["detections"]]
    return role, detections
```

Change `remember` to accept and store the role:

```python
    async def remember(
        self,
        thread_id: str,
        message: str,
        detections: list[Detection],
        role: MessageRole = MessageRole.USER,
    ) -> None:
        """Cache the detections found in a message, replacing any prior entry."""
        digest_message = self._hasher.hash(message)
        key = self._message_key(thread_id, digest_message)
        json_detections = _dumps(role, detections)

        blob = self._cipher.encrypt(json_detections)
        is_new = not await self._client.exists(key)

        await self._client.set(key, blob, ex=self._ttl)

        if is_new:
            index_key = self._index_key(thread_id)
            await self._client.rpush(index_key, digest_message)
            if self._ttl is not None:
                await self._client.expire(index_key, self._ttl)
```

Change `get_detections` to unpack the role and keep returning detections only:

```python
    async def get_detections(
        self,
        thread_id: str,
        message: str | None = None,
    ) -> list[Detection] | None:
        """Return a thread's detections, for one message or the whole thread."""
        if message is not None:
            digest_message = self._hasher.hash(message)
            key = self._message_key(thread_id, digest_message)
            blob = await self._client.get(key)
            if blob is None:
                return None
            json_detections = self._cipher.decrypt(_as_bytes(blob))
            _, detections = _loads(json_detections)
            return detections

        detections: list[Detection] = []
        for digest_message in await self._digests(thread_id):
            key = self._message_key(thread_id, digest_message)
            blob = await self._client.get(key)
            if blob is not None:
                json_detections = self._cipher.decrypt(_as_bytes(blob))
                _, message_detections = _loads(json_detections)
                detections.extend(message_detections)

        return detections
```

Add `get_provenance` after `get_detections`:

```python
    async def get_provenance(self, thread_id: str) -> dict[str, MessageRole]:
        """Return the first-occurrence role of every value in the thread."""
        provenance: dict[str, MessageRole] = {}

        for digest_message in await self._digests(thread_id):
            key = self._message_key(thread_id, digest_message)
            blob = await self._client.get(key)
            if blob is None:
                continue
            json_detections = self._cipher.decrypt(_as_bytes(blob))
            role, detections = _loads(json_detections)
            for detection in detections:
                provenance.setdefault(detection.text.casefold(), role)

        return provenance
```

Change the `forget` decrypt-and-count branch to unpack the role:

```python
            if blob is not None:
                messages += 1
                json_detections = self._cipher.decrypt(_as_bytes(blob))
                _, loaded = _loads(json_detections)
                detections += len(loaded)
```

- [ ] **Step 4: Run to verify it passes**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/conversation_memory/test_redis.py -q`
Expected: PASS (existing tests plus the new provenance class). Requires `fakeredis` and `cryptography`; if absent the class is skipped by `importorskip`.

- [ ] **Step 5: Lint and typecheck**

Run: `uv run --no-sync ruff format src/piighost/conversation_memory/redis_backend.py tests/conversation_memory/test_redis.py -q && uv run --no-sync ruff check src/piighost/conversation_memory/redis_backend.py && uv run --no-sync pyrefly check src/piighost/conversation_memory/redis_backend.py`
Expected: All checks passed, 0 errors.

- [ ] **Step 6: Commit**

```bash
git add src/piighost/conversation_memory/redis_backend.py tests/conversation_memory/test_redis.py
git commit -m "feat(memory): record provenance in the Redis backend"
```

---

## Task 4: Pipeline role and provenance filter

**Files:**
- Modify: `src/piighost/pipeline/thread.py`
- Test: `tests/pipeline/test_thread.py`

- [ ] **Step 1: Write the failing tests**

Add to the top imports of `tests/pipeline/test_thread.py`:

```python
from piighost.conversation_memory import InMemoryConversationMemory, MessageRole
```

(Replace the existing `from piighost.conversation_memory import InMemoryConversationMemory` line.)

Add a new test class at the end of the file:

```python
class TestProvenance:
    async def test_assistant_introduced_value_stays_clear(self) -> None:
        """A value the assistant introduces first is not anonymized."""
        pipeline = _pipeline()
        result = await pipeline.anonymize("It is Emma", "t1", MessageRole.ASSISTANT)
        assert result.text == "It is Emma"

    async def test_user_reference_after_assistant_stays_clear(self) -> None:
        """A user reference to an assistant-introduced value stays in clear."""
        pipeline = _pipeline()
        await pipeline.anonymize("It is Emma", "t1", MessageRole.ASSISTANT)
        result = await pipeline.anonymize("what about Emma", "t1", MessageRole.USER)
        assert result.text == "what about Emma"

    async def test_user_introduced_value_is_anonymized(self) -> None:
        """A value the user introduces first is anonymized as before."""
        pipeline = _pipeline()
        result = await pipeline.anonymize("I am Emma", "t1", MessageRole.USER)
        assert result.text == "I am <<PERSON:1>>"

    async def test_assistant_repeat_after_user_stays_anonymized(self) -> None:
        """A user-introduced value stays anonymized when the assistant repeats it."""
        pipeline = _pipeline()
        await pipeline.anonymize("I am Emma", "t1", MessageRole.USER)
        result = await pipeline.anonymize("Hello Emma", "t1", MessageRole.ASSISTANT)
        assert result.text == "Hello <<PERSON:1>>"

    async def test_default_role_anonymizes(self) -> None:
        """Omitting the role treats the message as user PII."""
        pipeline = _pipeline()
        result = await pipeline.anonymize("I am Emma", "t1")
        assert result.text == "I am <<PERSON:1>>"
```

- [ ] **Step 2: Run to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/pipeline/test_thread.py::TestProvenance -q`
Expected: FAIL, `anonymize` does not accept a role and assistant values are still anonymized.

- [ ] **Step 3: Implement role and provenance filtering**

In `src/piighost/pipeline/thread.py`, add `MessageRole` to the conversation_memory import:

```python
from piighost.conversation_memory.base import (
    AnyConversationMemory,
    Forgotten,
    MessageRole,
)
```

Replace `anonymize`, `_detect`, and `_thread_tokens` with:

```python
    async def anonymize(
        self,
        text: str,
        thread_id: str,
        role: MessageRole = MessageRole.USER,
    ) -> Anonymization[PreservationT]:
        """Anonymize a message with tokens consistent across its thread.

        The thread_id is required: there is no shared default, so two callers
        cannot fall into one thread and leak each other's PII. The role dates the
        values the message introduces: a value first introduced by the assistant
        is left in clear, since it is not user PII.

        Raises:
            PIIRemainingError: If a guard flags PII left in the output.
        """
        detections = await self._detect(text, thread_id, role)
        thread_tokens = await self._thread_tokens(thread_id)
        token_of = {
            detection: token
            for entity, token in thread_tokens.items()
            for detection in entity.detections
        }

        message_entities = self.linker.link(detections)
        message_tokens = {
            entity: token_of[entity.detections[0]]
            for entity in message_entities
            if entity.detections[0] in token_of
        }
        rendered = self.anonymizer.render(text, message_entities, message_tokens)

        await self._guard(rendered)
        return Anonymization(text=rendered, tokens=message_tokens)
```

Note: `preserved` and the two-argument `_guard(rendered, preserved)` call are added in Task 5. In this task the guard is called with one argument, so a pipeline configured with a guard is unaffected here (the default `_pipeline()` in these tests uses no guard).

```python
    async def _detect(
        self,
        text: str,
        thread_id: str,
        role: MessageRole = MessageRole.USER,
    ) -> list[Detection]:
        """Return a message's detections, from cache or a fresh cleaned detection."""
        cached = await self.memory.get_detections(thread_id, text)

        if cached is not None:
            return cached

        detections = await self.detector.detect(text)
        detections = self._resolve_overlaps(detections)
        detections = self._expand(text, detections)
        await self.memory.remember(
            message=text,
            thread_id=thread_id,
            detections=detections,
            role=role,
        )
        return detections
```

```python
    async def _thread_tokens(self, thread_id: str) -> Mapping[Entity, PreservationT]:
        """Assign a token to every anonymizable entity across the thread.

        An entity whose value was first introduced by the assistant is left out,
        so it gets no token and stays in clear.
        """
        union = await self.memory.get_detections(thread_id) or []
        entities = self.linker.link(union)
        thread_entities = self._resolve_entities(entities)
        provenance = await self.memory.get_provenance(thread_id)

        anonymizable = [
            entity
            for entity in thread_entities
            if provenance.get(entity.text.casefold()) is not MessageRole.ASSISTANT
        ]
        return self.anonymizer.create(anonymizable)
```

- [ ] **Step 4: Run to verify it passes**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/pipeline/test_thread.py -q`
Expected: PASS (existing thread tests plus `TestProvenance`).

- [ ] **Step 5: Lint and typecheck**

Run: `uv run --no-sync ruff format src/piighost/pipeline/thread.py tests/pipeline/test_thread.py -q && uv run --no-sync ruff check src/piighost/pipeline/thread.py && uv run --no-sync pyrefly check src/piighost/pipeline/thread.py`
Expected: All checks passed, 0 errors.

- [ ] **Step 6: Commit**

```bash
git add src/piighost/pipeline/thread.py tests/pipeline/test_thread.py
git commit -m "feat(pipeline): preserve assistant-introduced values by provenance"
```

---

## Task 5: Guard exemption for preserved values

**Files:**
- Modify: `src/piighost/pipeline/base.py`
- Modify: `src/piighost/pipeline/thread.py`
- Test: `tests/pipeline/test_thread.py`

- [ ] **Step 1: Write the failing test**

Add to the top imports of `tests/pipeline/test_thread.py`:

```python
from piighost.components.guard import DetectorGuardRail
```

Add to the `TestProvenance` class:

```python
    async def test_a_guard_does_not_flag_a_preserved_value(self) -> None:
        """A preserved assistant value is exempt from the guard, not flagged."""
        memory = InMemoryConversationMemory()
        pipeline = ThreadAnonymizationPipeline(
            ExactMatchDetector({"Emma": "PERSON", "Liam": "PERSON"}),
            ExactEntityLinker(),
            Anonymizer(LabelCounterPlaceholderFactory()),
            memory,
            guard=DetectorGuardRail(ExactMatchDetector({"Emma": "PERSON"})),
        )
        result = await pipeline.anonymize("It is Emma", "t1", MessageRole.ASSISTANT)
        assert result.text == "It is Emma"

    async def test_a_guard_still_flags_real_residual_pii(self) -> None:
        """A residual value that was not preserved still trips the guard."""
        from piighost.exceptions import PIIRemainingError

        memory = InMemoryConversationMemory()
        pipeline = ThreadAnonymizationPipeline(
            ExactMatchDetector({"Emma": "PERSON"}),
            ExactEntityLinker(),
            Anonymizer(LabelCounterPlaceholderFactory()),
            memory,
            guard=DetectorGuardRail(ExactMatchDetector({"Liam": "PERSON"})),
        )
        with pytest.raises(PIIRemainingError):
            await pipeline.anonymize("Liam is here", "t1", MessageRole.ASSISTANT)
```

Add `import pytest` to the top of the test file if not present (it is not currently imported there, so add it).

- [ ] **Step 2: Run to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest "tests/pipeline/test_thread.py::TestProvenance::test_a_guard_does_not_flag_a_preserved_value" -q`
Expected: FAIL with `PIIRemainingError`, the guard re-detects the preserved Emma.

- [ ] **Step 3: Add the exempt set to the guard**

In `src/piighost/pipeline/base.py`, add `replace` to the dataclasses import at the top:

```python
from collections.abc import Mapping
from dataclasses import replace
from typing import Generic, Protocol, runtime_checkable
```

Replace `_guard`:

```python
    async def _guard(
        self, text: str, expected: frozenset[str] = frozenset()
    ) -> None:
        """Raise PIIRemainingError when the guard flags unexpected PII.

        Values in expected are ones the pipeline chose to leave in clear, such as
        an entity the assistant introduced. A detector-based guard would re-find
        them, so they are dropped from the verdict before deciding. A score-based
        guard localizes nothing, so it cannot be filtered this way.
        """
        if self.guard is None:
            return

        verdict = await self.guard.check(text)

        if verdict.detections:
            residual = tuple(
                detection
                for detection in verdict.detections
                if detection.text.casefold() not in expected
            )
            if not residual:
                return
            verdict = replace(verdict, detections=residual)

        if verdict.flagged:
            raise _pii_remaining(verdict)
```

In `src/piighost/pipeline/thread.py`, add the `preserved` local and pass it to `_guard`. Keep the existing `anonymizable = list(message_tokens)` render line from Task 4 (Anonymizer.render looks up `tokens[entity]` for every entity it is given, so only the tokenized entities may be passed). The tail of `anonymize` becomes:

```python
        message_tokens = {
            entity: token_of[entity.detections[0]]
            for entity in message_entities
            if entity.detections[0] in token_of
        }
        preserved = frozenset(
            entity.text.casefold()
            for entity in message_entities
            if entity.detections[0] not in token_of
        )
        anonymizable = list(message_tokens)
        rendered = self.anonymizer.render(text, anonymizable, message_tokens)

        await self._guard(rendered, preserved)
        return Anonymization(text=rendered, tokens=message_tokens)
```

- [ ] **Step 4: Run to verify it passes**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/pipeline/test_thread.py -q`
Expected: PASS.

- [ ] **Step 5: Lint and typecheck**

Run: `uv run --no-sync ruff format src/piighost/pipeline tests/pipeline/test_thread.py -q && uv run --no-sync ruff check src/piighost/pipeline && uv run --no-sync pyrefly check src/piighost/pipeline`
Expected: All checks passed, 0 errors.

- [ ] **Step 6: Commit**

```bash
git add src/piighost/pipeline/base.py src/piighost/pipeline/thread.py tests/pipeline/test_thread.py
git commit -m "feat(pipeline): exempt preserved values from the guard"
```

---

## Task 6: AssistantEntityStrategy enum

**Files:**
- Modify: `src/piighost/integrations/middleware/strategy.py`
- Modify: `src/piighost/integrations/middleware/__init__.py`
- Modify: `tests/regression/test_imports.py`

- [ ] **Step 1: Add the PUBLIC_API regression entry (failing test)**

In `tests/regression/test_imports.py`, add next to the other middleware entries:

```python
    ("piighost.integrations.middleware", "AssistantEntityStrategy"),
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --no-sync pytest tests/regression/test_imports.py -q`
Expected: FAIL on the `AssistantEntityStrategy` case.

- [ ] **Step 3: Add the enum and export it**

In `src/piighost/integrations/middleware/strategy.py`, add after `InventedPlaceholderStrategy`:

```python
class AssistantEntityStrategy(Enum):
    """How the middleware treats entities the assistant introduces.

    A value's provenance is the role of its first occurrence in the thread. A
    value the assistant introduced is not user PII, so anonymizing it strips the
    model of its world knowledge of that entity.

    - PRESERVE: leave assistant-introduced values in clear.
    - ANONYMIZE: anonymize them like user PII.
    - IGNORE: do not analyze assistant messages at all, saving the detector.
    """

    PRESERVE = "preserve"
    ANONYMIZE = "anonymize"
    IGNORE = "ignore"
```

In `src/piighost/integrations/middleware/__init__.py`, add `AssistantEntityStrategy` to the strategy import and to `__all__` (keep it sorted):

```python
from piighost.integrations.middleware.strategy import (
    AssistantEntityStrategy,
    InventedPlaceholderStrategy,
    ToolCallStrategy,
)

__all__ = [
    "AssistantEntityStrategy",
    "InventedPlaceholderStrategy",
    "PIIAnonymizationMiddleware",
    "ToolCallStrategy",
]
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --no-sync pytest tests/regression/test_imports.py -q`
Expected: PASS.

- [ ] **Step 5: Lint and typecheck**

Run: `uv run --no-sync ruff format src/piighost/integrations/middleware/strategy.py src/piighost/integrations/middleware/__init__.py -q && uv run --no-sync ruff check src/piighost/integrations/middleware && uv run --no-sync pyrefly check src/piighost/integrations/middleware`
Expected: All checks passed, 0 errors.

- [ ] **Step 6: Commit**

```bash
git add src/piighost/integrations/middleware/strategy.py src/piighost/integrations/middleware/__init__.py tests/regression/test_imports.py
git commit -m "feat(middleware): add AssistantEntityStrategy"
```

---

## Task 7: Middleware role mapping

**Files:**
- Modify: `src/piighost/integrations/middleware/langchain.py`
- Test: `tests/integrations/middleware/test_middleware.py`

- [ ] **Step 1: Write the failing tests**

Add to the top imports of `tests/integrations/middleware/test_middleware.py`:

```python
from piighost.integrations.middleware import (
    AssistantEntityStrategy,
    InventedPlaceholderStrategy,
    ToolCallStrategy,
)
```

(Replace the existing `from piighost.integrations.middleware import (...)` block, keeping `InventedPlaceholderStrategy` and `ToolCallStrategy`.)

Add a new test class at the end of the file:

```python
class TestAssistantProvenance:
    def _middleware(
        self, monkeypatch: pytest.MonkeyPatch, strategy: AssistantEntityStrategy
    ) -> Any:
        """Build the middleware under an assistant-entity strategy."""
        module = importlib.import_module(_MODULE)
        monkeypatch.setattr(
            module, "get_config", lambda: {"configurable": {"thread_id": "t1"}}
        )
        return module.PIIAnonymizationMiddleware(
            _pipeline(), assistant_strategy=strategy
        )

    async def _assistant_then_user(self, middleware: Any) -> str:
        """Let the assistant introduce Emma, then anonymize a user reference."""
        from langchain_core.messages import AIMessage, HumanMessage

        await middleware.abefore_model({"messages": [AIMessage("It is Emma")]}, None)
        state = {"messages": [HumanMessage("what about Emma")]}
        await middleware.abefore_model(state, None)
        return state["messages"][0].content

    async def test_preserve_keeps_assistant_value_clear(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Under PRESERVE, a user reference to an assistant value stays in clear."""
        pytest.importorskip("langchain")
        middleware = self._middleware(monkeypatch, AssistantEntityStrategy.PRESERVE)
        assert await self._assistant_then_user(middleware) == "what about Emma"

    async def test_anonymize_treats_assistant_value_as_pii(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Under ANONYMIZE, an assistant-introduced value is anonymized."""
        pytest.importorskip("langchain")
        middleware = self._middleware(monkeypatch, AssistantEntityStrategy.ANONYMIZE)
        assert await self._assistant_then_user(middleware) == "what about <<PERSON:1>>"

    async def test_ignore_does_not_analyze_assistant_messages(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Under IGNORE, an assistant message is left untouched."""
        pytest.importorskip("langchain")
        from langchain_core.messages import AIMessage

        middleware = self._middleware(monkeypatch, AssistantEntityStrategy.IGNORE)
        update = await middleware.abefore_model(
            {"messages": [AIMessage("It is Emma")]}, None
        )
        assert update is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/integrations/middleware/test_middleware.py::TestAssistantProvenance -q`
Expected: FAIL, `PIIAnonymizationMiddleware` rejects `assistant_strategy`.

- [ ] **Step 3: Implement role mapping in the middleware**

In `src/piighost/integrations/middleware/langchain.py`, update the piighost imports near the top (before the langchain guard):

```python
from piighost.components.placeholder.base import BaseDelimitedPlaceholderFactory
from piighost.components.placeholder.tags import PreservesIdentity
from piighost.conversation_memory import MessageRole
from piighost.exceptions import InventedPlaceholderError
from piighost.integrations.middleware.strategy import (
    AssistantEntityStrategy,
    InventedPlaceholderStrategy,
    ToolCallStrategy,
)
from piighost.pipeline import ThreadAnonymizationPipeline
```

Add `BaseMessage` to the langchain_core.messages import (after the guard):

```python
from langchain_core.messages import (  # noqa: E402
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
```

Change `__init__` to accept the strategy:

```python
    def __init__(
        self,
        pipeline: ThreadAnonymizationPipeline[IdentityT],
        tool_strategy: ToolCallStrategy = ToolCallStrategy.FULL,
        require_thread_id: bool = True,
        invented_strategy: InventedPlaceholderStrategy = InventedPlaceholderStrategy.RAISE,
        assistant_strategy: AssistantEntityStrategy = AssistantEntityStrategy.PRESERVE,
    ) -> None:
        """Store the pipeline, the strategies, and the thread-id policy.

        require_thread_id defaults to True so a missing thread id raises rather
        than routing every conversation into the shared default thread and
        leaking placeholders across them. Pass False to opt into that shared
        fallback knowingly, for single-conversation or stateless use.

        invented_strategy defaults to RAISE so a token the pipeline never issued,
        surfacing in a deanonymized model reply or tool argument, is refused
        rather than passed on. Pass KEEP or DROP to tolerate it instead.

        assistant_strategy defaults to PRESERVE so a value the assistant
        introduced is left in clear, keeping the model's world knowledge of it.
        Pass ANONYMIZE to tokenize it anyway, or IGNORE to skip analyzing
        assistant messages entirely and save the detector.
        """
        super().__init__()
        self._pipeline = pipeline
        self.tool_strategy = tool_strategy
        self._require_thread_id = require_thread_id
        self._invented_strategy = invented_strategy
        self.assistant_strategy = assistant_strategy
```

Replace `abefore_model`:

```python
    async def abefore_model(
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        """Anonymize the user and model messages before the model sees them."""
        thread_id = _thread_id(self._require_thread_id)
        allowed: tuple[type, ...] = (HumanMessage, AIMessage)

        if self.assistant_strategy is AssistantEntityStrategy.IGNORE:
            # IGNORE skips assistant analysis entirely, so its messages are not
            # sent through anonymization at all, saving the detector.
            allowed = (HumanMessage,)

        if self.tool_strategy is ToolCallStrategy.INPUT:
            # INPUT left the tool response raw, so anonymize it here before the
            # model sees it, unlike OUTPUT/FULL which already anonymized it.
            allowed = (*allowed, ToolMessage)

        async def anonymize(message: BaseMessage, content: str) -> str:
            """Anonymize one message under the role its type contributes."""
            role = self._message_role(message)
            return await self._anonymize(content, thread_id, role)

        return await self._rewrite(state, allowed, anonymize)
```

Replace `aafter_model`'s call to use the new transform signature (message, content):

```python
    async def aafter_model(
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        """Deanonymize the user and model messages for display."""
        thread_id = _thread_id(self._require_thread_id)

        async def restore(message: BaseMessage, content: str) -> str:
            """Deanonymize one message's content for display."""
            return await self._deanonymize(content, thread_id)

        return await self._rewrite(state, (HumanMessage, AIMessage), restore)
```

Replace `_rewrite` so the transform receives the message and its string content:

```python
    async def _rewrite(
        self,
        state: AgentState,
        allowed: tuple[type, ...],
        transform: Callable[[BaseMessage, str], Awaitable[str]],
    ) -> dict[str, Any] | None:
        """Apply transform to each allowed message's text, in place."""
        changed = False
        messages = state["messages"]

        for message in messages:
            content = message.content
            if not isinstance(message, allowed) or not isinstance(content, str):
                continue

            rewritten = await transform(message, content)
            if rewritten != content:
                message.content = rewritten
                changed = True

        return {"messages": messages} if changed else None
```

Add `_message_role`, and give `_anonymize` a role, near the other private helpers:

```python
    def _message_role(self, message: BaseMessage) -> MessageRole:
        """Return the provenance role a message contributes.

        An AIMessage is ASSISTANT under PRESERVE, but USER under ANONYMIZE so its
        values are anonymized like user PII. Everything else counts as USER.
        """
        if not isinstance(message, AIMessage):
            return MessageRole.USER
        if self.assistant_strategy is AssistantEntityStrategy.ANONYMIZE:
            return MessageRole.USER
        return MessageRole.ASSISTANT

    async def _anonymize(
        self, text: str, thread_id: str, role: MessageRole = MessageRole.USER
    ) -> str:
        """Anonymize a text within the thread and return the anonymized string."""
        result = await self._pipeline.anonymize(text, thread_id, role)
        return result.text
```

- [ ] **Step 4: Run to verify it passes**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/integrations/middleware/test_middleware.py -q`
Expected: PASS (existing middleware tests plus `TestAssistantProvenance`).

- [ ] **Step 5: Lint and typecheck**

Run: `uv run --no-sync ruff format src/piighost/integrations/middleware/langchain.py tests/integrations/middleware/test_middleware.py -q && uv run --no-sync ruff check src/piighost/integrations/middleware && uv run --no-sync pyrefly check src/piighost/integrations/middleware`
Expected: All checks passed, 0 errors.

- [ ] **Step 6: Commit**

```bash
git add src/piighost/integrations/middleware/langchain.py tests/integrations/middleware/test_middleware.py
git commit -m "feat(middleware): map message roles for assistant-entity provenance"
```

---

## Task 8: Example

**Files:**
- Create: `examples/langchain_assistant_provenance.py`

- [ ] **Step 1: Write the example**

Create `examples/langchain_assistant_provenance.py`:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost[middleware]"]
#
# [tool.uv.sources]
# piighost = { path = "..", editable = true }
# ///
"""Preserve entities the assistant introduces, under each strategy.

A value the model itself names, say a public figure like Napoleon, is not user
PII. Anonymizing it would strip the model of its world knowledge of that entity.
The provenance rule keys on a value's first occurrence in the thread: introduced
by the assistant, it is left in clear; introduced by the user, it stays
anonymized. AssistantEntityStrategy chooses the behavior:

  PRESERVE   leave assistant-introduced values in clear (default)
  ANONYMIZE  anonymize them like user PII
  IGNORE     do not analyze assistant messages at all, saving the detector

Here the assistant first names Napoleon, then the user asks about him. The
example anonymizes that user turn under each strategy and prints what the model
would receive. Run with:
uv run examples/langchain_assistant_provenance.py
"""

import asyncio

from langchain_core.messages import AIMessage, HumanMessage

from piighost.components.anonymizer import Anonymizer
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.pipeline import ThreadAnonymizationPipeline
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.integrations.middleware import (
    AssistantEntityStrategy,
    PIIAnonymizationMiddleware,
)
import piighost.integrations.middleware.langchain as middleware_module


def _middleware(strategy: AssistantEntityStrategy) -> PIIAnonymizationMiddleware:
    """Build the middleware over a fresh pipeline under one strategy."""
    pipeline = ThreadAnonymizationPipeline(
        ExactMatchDetector({"Napoleon": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(LabelCounterPlaceholderFactory()),
        InMemoryConversationMemory(),
    )
    return PIIAnonymizationMiddleware(pipeline, assistant_strategy=strategy)


async def _run_once(strategy: AssistantEntityStrategy) -> str:
    """Let the assistant name Napoleon, then anonymize the user's follow-up."""
    middleware_module.get_config = lambda: {"configurable": {"thread_id": "t1"}}
    middleware = _middleware(strategy)

    await middleware.abefore_model({"messages": [AIMessage("It was Napoleon.")]}, None)
    state = {"messages": [HumanMessage("What did Napoleon do?")]}
    await middleware.abefore_model(state, None)
    return state["messages"][0].content


async def main() -> None:
    """Anonymize the user's Napoleon question under every strategy."""
    print("assistant introduced: 'It was Napoleon.'")
    print("user then asks:        'What did Napoleon do?'\n")

    strategies = [
        AssistantEntityStrategy.PRESERVE,
        AssistantEntityStrategy.ANONYMIZE,
        AssistantEntityStrategy.IGNORE,
    ]
    for strategy in strategies:
        seen = await _run_once(strategy)
        print(f"  {strategy.name:9} -> model sees: {seen!r}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run the example**

Run: `uv run examples/langchain_assistant_provenance.py`
Expected output:

```
assistant introduced: 'It was Napoleon.'
user then asks:        'What did Napoleon do?'

  PRESERVE  -> model sees: 'What did Napoleon do?'
  ANONYMIZE -> model sees: 'What did <<PERSON:1>> do?'
  IGNORE    -> model sees: 'What did <<PERSON:1>> do?'
```

(Under IGNORE the assistant message is not analyzed, so Napoleon is first recorded from the user turn as USER provenance and anonymized.)

- [ ] **Step 3: Lint**

Run: `uv run --no-sync ruff format examples/langchain_assistant_provenance.py -q && uv run --no-sync ruff check examples/langchain_assistant_provenance.py`
Expected: All checks passed.

- [ ] **Step 4: Commit**

```bash
git add examples/langchain_assistant_provenance.py
git commit -m "docs(examples): add an assistant-provenance example"
```

---

## Task 9: Blueprint decision journal

**Files:**
- Modify: `design/rewrite-blueprint.md`

- [ ] **Step 1: Add the decision entry**

In `design/rewrite-blueprint.md`, in the decision-journal table (the one holding the `Placeholder inventé par le LLM` row), add a new row:

```markdown
| Provenance d'entité | Implémenté. Une valeur dont la première occurrence dans le thread vient d'un message assistant n'est pas anonymisée (elle n'est pas de la PII user, la tokeniser priverait le modèle de sa connaissance du monde). Provenance enregistrée dans la ConversationMemory (`remember(role)` + `get_provenance`), indexée par valeur casefold en ordre first-seen. Enum `AssistantEntityStrategy` (`PRESERVE` défaut / `ANONYMIZE` / `IGNORE`) sur le middleware, câblée uniquement par le rôle transmis au pipeline. Valeurs préservées exemptées d'un détecteur-guard. Hors périmètre v1 : ToolMessage, scoping par label, config TOML, guard par score. |
```

- [ ] **Step 2: Run the full suite and full lint**

```bash
find src tests -name __pycache__ -type d -exec rm -rf {} +
uv run --no-sync pytest -q
uv run --no-sync ruff format src/piighost tests -q
uv run --no-sync ruff check src/piighost tests
uv run --no-sync pyrefly check src/piighost
uv run --no-sync bandit -q -c pyproject.toml -r src/piighost
```

Expected: all tests pass, ruff clean, pyrefly 0 errors, bandit no issues.

- [ ] **Step 3: Commit**

```bash
git add design/rewrite-blueprint.md
git commit -m "docs(blueprint): record the entity-provenance decision"
```

---

## Final verification

- [ ] Full suite green: `uv run --no-sync pytest -q`.
- [ ] `python -c "from piighost.conversation_memory import MessageRole; from piighost.integrations.middleware import AssistantEntityStrategy"` succeeds.
- [ ] The example prints the expected three lines.
- [ ] ruff, pyrefly, bandit clean across `src/piighost`.
