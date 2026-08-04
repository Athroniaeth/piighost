# Remote Thread Pipeline Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `AnyThreadPipeline` port and a `PIIGhostClient` that implements it over HTTP, so the middleware and any consumer run against a local or remote thread pipeline interchangeably.

**Architecture:** A `recognizer` property is lifted onto the thread-pipeline port so the middleware reads the token grammar instead of introspecting `anonymizer.factory`. `PIIGhostClient` (behind the `client` extra, injecting or building an `httpx.AsyncClient`) implements the four thread methods plus `recognizer`, returning empty-token `Anonymization`s since the server owns the mapping.

**Tech Stack:** Python 3.11+, httpx (extra `client`, installed in the dev venv), pytest (`asyncio_mode = "auto"`, `httpx.MockTransport` for a fake server).

---

## Conventions for every task

- Run tests with `uv run --no-sync`. Before each pytest run clear bytecode: `find src tests -name __pycache__ -type d -exec rm -rf {} +`.
- `asyncio_mode = "auto"`: `async def test_...` needs NO decorator. ANN enforced on tests.
- Python 3.11+ native typing, NO `from __future__ import annotations`. Docstrings plain prose plus bullet lists only. English only. Conventional Commits.
- No pyrefly suppression is expected; `pyrefly check src/piighost` must stay 0. If pyrefly flags the empty-token `Anonymization` typing, report it rather than suppressing.

## File structure

- Modify `src/piighost/pipeline/base.py` — add the `AnyThreadPipeline` port (Task 1).
- Modify `src/piighost/pipeline/thread.py` — add the `recognizer` property (Task 1).
- Modify `src/piighost/pipeline/__init__.py` — export `AnyThreadPipeline` (Task 1).
- Modify `src/piighost/integrations/middleware/langchain.py` — read `recognizer`, type on the port (Task 2).
- Modify `src/piighost/exceptions.py` — `ClientError`, `RemoteError` (Task 3).
- Create `src/piighost/integrations/client/remote.py` — `PIIGhostClient` (Task 3).
- Create `src/piighost/integrations/client/__init__.py` — lazy export (Task 3).
- Modify `tests/regression/test_imports.py` — new public symbols (Task 4).
- Tests: `tests/pipeline/test_thread_recognizer.py`, `tests/integrations/client/test_client.py`, plus a middleware test edit.

Note: the spec sketched `integrations/client/{base,httpx}.py`; this plan uses `remote.py` for the class to avoid a module named `httpx.py` shadowing the `httpx` package, and needs no `base.py` since the port lives in `pipeline/base.py`.

---

### Task 1: AnyThreadPipeline port and recognizer property

**Files:**
- Modify: `src/piighost/pipeline/base.py`
- Modify: `src/piighost/pipeline/thread.py`
- Modify: `src/piighost/pipeline/__init__.py`
- Test: `tests/pipeline/test_thread_recognizer.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/pipeline/test_thread_recognizer.py`:

```python
"""Tests for the thread-pipeline port and its token-grammar recognizer."""

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import (
    LabelCounterPlaceholderFactory,
    MaskPlaceholderFactory,
)
from piighost.components.placeholder.base import BaseDelimitedPlaceholderFactory
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.pipeline import AnyThreadPipeline, ThreadAnonymizationPipeline


def _pipeline(factory: object) -> ThreadAnonymizationPipeline:
    """Build a thread pipeline over the given placeholder factory."""
    return ThreadAnonymizationPipeline(
        ExactMatchDetector({"Emma": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(factory),
        InMemoryConversationMemory(),
    )


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """ThreadAnonymizationPipeline is an AnyThreadPipeline."""
        pipeline = _pipeline(LabelCounterPlaceholderFactory())
        assert isinstance(pipeline, AnyThreadPipeline)


class TestRecognizer:
    def test_a_delimited_factory_is_its_own_recognizer(self) -> None:
        """A delimited factory is returned as the recognizer."""
        factory = LabelCounterPlaceholderFactory()
        pipeline = _pipeline(factory)
        assert pipeline.recognizer is factory
        assert isinstance(pipeline.recognizer, BaseDelimitedPlaceholderFactory)

    def test_a_mask_factory_has_no_recognizer(self) -> None:
        """A non-delimited factory yields no recognizer."""
        pipeline = _pipeline(MaskPlaceholderFactory())
        assert pipeline.recognizer is None
```

- [ ] **Step 2: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/pipeline/test_thread_recognizer.py -q`
Expected: FAIL with `ImportError: cannot import name 'AnyThreadPipeline'`.

- [ ] **Step 3: Add the port and the property**

In `src/piighost/pipeline/base.py`, add these imports (sorted into the existing groups):

```python
from piighost.components.placeholder.base import BaseDelimitedPlaceholderFactory
from piighost.conversation_memory.base import Forgotten, MessageRole
```

After the `AnyPipeline` protocol class, add the thread port:

```python
@runtime_checkable
class AnyThreadPipeline(Protocol[PreservationT_co]):
    """A thread-scoped pipeline, local or remote, anonymizing a conversation.

    It anonymizes each message of a thread with tokens stable across the thread,
    re-anonymizes a human-corrected message, deanonymizes any text carrying the
    thread's tokens, and forgets a thread wholesale. It also exposes the grammar
    of the tokens it emits, so a consumer such as the middleware can find them
    again without reaching into a local anonymizer, which a remote pipeline does
    not have.
    """

    async def anonymize(
        self, text: str, thread_id: str, role: "MessageRole" = MessageRole.USER
    ) -> Anonymization[PreservationT_co]:
        """Return the anonymized message and the token used for each entity."""
        ...

    async def anonymize_corrected(
        self, text: str, thread_id: str, detections: list[Detection]
    ) -> Anonymization[PreservationT_co]:
        """Re-anonymize a user message with a human-corrected detection set."""
        ...

    async def deanonymize(self, text: str, thread_id: str) -> str:
        """Return the text with every token from the thread replaced by its value."""
        ...

    async def forget_thread(self, thread_id: str) -> "Forgotten":
        """Erase a thread's memory and report how much was dropped."""
        ...

    @property
    def recognizer(self) -> "BaseDelimitedPlaceholderFactory | None":
        """The grammar of the tokens this pipeline emits, or None if none."""
        ...
```

In `src/piighost/pipeline/thread.py`, add the import (sorted):

```python
from piighost.components.placeholder.base import BaseDelimitedPlaceholderFactory
```

and add this property to `ThreadAnonymizationPipeline` (after `__init__`, before `anonymize`):

```python
    @property
    def recognizer(self) -> BaseDelimitedPlaceholderFactory | None:
        """The grammar of the tokens this pipeline emits, or None if none.

        A delimited factory is its own recognizer, since its tokens carry a
        grammar that can be found again; a factory without one, such as a mask,
        has no recognizer.
        """
        factory = self.anonymizer.factory
        if isinstance(factory, BaseDelimitedPlaceholderFactory):
            return factory
        return None
```

In `src/piighost/pipeline/__init__.py`, add `AnyThreadPipeline` to the import from `piighost.pipeline.base` and to `__all__` (alphabetical).

- [ ] **Step 4: Run it to verify it passes**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/pipeline/test_thread_recognizer.py -q`
Expected: PASS, 3 passed.

- [ ] **Step 5: Lint, types, commit**

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean, pyrefly 0 errors.

```bash
git add src/piighost/pipeline/base.py src/piighost/pipeline/thread.py src/piighost/pipeline/__init__.py tests/pipeline/test_thread_recognizer.py
git commit -m "feat(pipeline): add the thread pipeline port and token recognizer"
```

---

### Task 2: Middleware reads the recognizer

**Files:**
- Modify: `src/piighost/integrations/middleware/langchain.py`
- Test: `tests/integrations/middleware/test_middleware.py`

- [ ] **Step 1: Add a failing test for the recognizer-based fail-fast**

In `tests/integrations/middleware/test_middleware.py`, inside the existing `TestFactoryContract` class (the one asserting a non-delimited factory is refused), add:

```python
    def test_reads_the_recognizer_from_the_pipeline(self) -> None:
        """The middleware takes its recognizer from the pipeline's property."""

        class _Remoteish:
            """A minimal pipeline exposing only what the middleware reads."""

            recognizer = LabelCounterPlaceholderFactory()

            async def anonymize(self, text, thread_id, role=MessageRole.USER):
                return None

            async def anonymize_corrected(self, text, thread_id, detections):
                return None

            async def deanonymize(self, text, thread_id):
                return text

            async def forget_thread(self, thread_id):
                return None

        middleware = PIIAnonymizationMiddleware(_Remoteish())
        assert middleware._recognizer is _Remoteish.recognizer

    def test_a_pipeline_without_a_recognizer_is_refused(self) -> None:
        """A pipeline whose recognizer is None fails fast at construction."""

        class _Unrecognizable:
            """A pipeline that emits no recognizable token grammar."""

            recognizer = None

        with pytest.raises(UnrecognizableFactoryError, match="recognizable"):
            PIIAnonymizationMiddleware(_Unrecognizable())
```

with, at the top of the test file, ensuring these imports exist (add any missing): `import pytest`, `from piighost.components.placeholder import LabelCounterPlaceholderFactory`, `from piighost.conversation_memory import MessageRole`, `from piighost.exceptions import UnrecognizableFactoryError`, and `PIIAnonymizationMiddleware` from `piighost.integrations.middleware.langchain`.

- [ ] **Step 2: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/integrations/middleware/test_middleware.py -q`
Expected: FAIL: the old middleware introspects `pipeline.anonymizer.factory`, so `_Remoteish`/`_Unrecognizable` (no `anonymizer`) do not behave as the new tests require.

- [ ] **Step 3: Rewire the middleware to the port and the recognizer**

In `src/piighost/integrations/middleware/langchain.py`:

Replace the `ThreadAnonymizationPipeline` import with the port:

```python
from piighost.pipeline import AnyThreadPipeline
```

Change the `IdentityT`-bound `__init__` parameter type from `ThreadAnonymizationPipeline[IdentityT]` to `AnyThreadPipeline[IdentityT]`.

Replace the fail-fast block (the `factory = getattr(pipeline.anonymizer, "factory", None)` lines through the `raise`) with:

```python
        # The IdentityT bound guarantees a recognizable grammar for typed
        # callers; re-check at runtime so an untyped or remote pipeline without
        # one fails loudly here, not silently when the invented-placeholder
        # strategy would have found nothing.
        recognizer = pipeline.recognizer
        if recognizer is None:
            raise UnrecognizableFactoryError(
                "PIIAnonymizationMiddleware needs a pipeline exposing a delimited "
                "token recognizer, whose tokens can be found again to detect "
                "invented ones; got a pipeline with no recognizable grammar."
            )

        self._pipeline = pipeline
        self._recognizer = recognizer
```

Delete the now-unused import of `BaseDelimitedPlaceholderFactory` if nothing else uses it in the module (check first; leave it if another reference remains).

- [ ] **Step 4: Run the middleware tests**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/integrations/middleware/ -q`
Expected: PASS, including the two new tests and every existing middleware test (they build the middleware on a real `ThreadAnonymizationPipeline`, which now exposes `recognizer`).

- [ ] **Step 5: Lint, types, full suite, commit**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest -q`
Expected: PASS.

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean, pyrefly 0 errors.

```bash
git add src/piighost/integrations/middleware/langchain.py tests/integrations/middleware/test_middleware.py
git commit -m "refactor(middleware): read the token recognizer from the pipeline port"
```

---

### Task 3: PIIGhostClient

**Files:**
- Modify: `src/piighost/exceptions.py`
- Create: `src/piighost/integrations/client/remote.py`
- Create: `src/piighost/integrations/client/__init__.py`
- Test: `tests/integrations/client/test_client.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/integrations/client/test_client.py`:

```python
"""Tests for the PIIGhostClient, a remote thread pipeline over HTTP."""

import json

import httpx
import pytest

from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.conversation_memory import Forgotten, MessageRole
from piighost.exceptions import RemoteError
from piighost.integrations.client import PIIGhostClient
from piighost.models import Detection, Span
from piighost.pipeline import AnyThreadPipeline


def _client(handler: object) -> PIIGhostClient:
    """Build a client over a MockTransport driven by handler."""
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url="http://api")
    return PIIGhostClient(http)


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """PIIGhostClient is an AnyThreadPipeline."""
        client = _client(lambda request: httpx.Response(200, json={}))
        assert isinstance(client, AnyThreadPipeline)


class TestAnonymize:
    async def test_posts_and_returns_empty_token_anonymization(self) -> None:
        """anonymize posts text, thread, role and returns the server text."""
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["path"] = request.url.path
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"anonymized_text": "Hi <<PERSON:1>>"})

        client = _client(handler)
        result = await client.anonymize("Hi Emma", "t1")
        assert seen["path"] == "/v1/anonymize"
        assert seen["body"] == {"text": "Hi Emma", "thread_id": "t1", "role": "user"}
        assert result.text == "Hi <<PERSON:1>>"
        assert result.tokens == {}

    async def test_serializes_the_role_value(self) -> None:
        """The role is sent as its enum value."""
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"anonymized_text": "x"})

        client = _client(handler)
        await client.anonymize("x", "t1", MessageRole.ASSISTANT)
        assert seen["body"]["role"] == "assistant"


class TestAnonymizeCorrected:
    async def test_posts_serialized_detections(self) -> None:
        """anonymize_corrected posts the corrected detections as dicts."""
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["path"] = request.url.path
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"anonymized_text": "<<PERSON:1>>"})

        client = _client(handler)
        detection = Detection(
            span=Span(0, 4), text="Emma", label="PERSON", confidence=1.0
        )
        result = await client.anonymize_corrected("Emma", "t1", [detection])
        assert seen["path"] == "/v1/anonymize/corrected"
        assert seen["body"]["detections"] == [detection.to_dict()]
        assert result.text == "<<PERSON:1>>"


class TestDeanonymize:
    async def test_posts_and_returns_the_restored_text(self) -> None:
        """deanonymize posts the tokenized text and returns the restored one."""
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["path"] = request.url.path
            return httpx.Response(200, json={"text": "Emma"})

        client = _client(handler)
        restored = await client.deanonymize("<<PERSON:1>>", "t1")
        assert seen["path"] == "/v1/deanonymize"
        assert restored == "Emma"


class TestForgetThread:
    async def test_deletes_and_returns_a_forgotten(self) -> None:
        """forget_thread deletes the thread and reports what was dropped."""
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["method"] = request.method
            seen["path"] = request.url.path
            return httpx.Response(200, json={"messages": 2, "detections": 5})

        client = _client(handler)
        forgotten = await client.forget_thread("t 1")
        assert seen["method"] == "DELETE"
        assert seen["path"] == "/v1/threads/t%201"
        assert forgotten == Forgotten(messages=2, detections=5)


class TestErrors:
    async def test_non_2xx_raises_remote_error(self) -> None:
        """A non-2xx response raises RemoteError with the status."""
        client = _client(lambda request: httpx.Response(503, text="down"))
        with pytest.raises(RemoteError, match="503"):
            await client.anonymize("x", "t1")


class TestRecognizer:
    def test_defaults_to_a_delimited_recognizer(self) -> None:
        """Without an override, the client declares the standard grammar."""
        from piighost.components.placeholder.base import (
            BaseDelimitedPlaceholderFactory,
        )

        client = _client(lambda request: httpx.Response(200, json={}))
        assert isinstance(client.recognizer, BaseDelimitedPlaceholderFactory)

    def test_recognizer_is_overridable(self) -> None:
        """A caller can declare the server's grammar explicitly."""
        factory = LabelCounterPlaceholderFactory()
        transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
        http = httpx.AsyncClient(transport=transport, base_url="http://api")
        client = PIIGhostClient(http, recognizer=factory)
        assert client.recognizer is factory


class TestLifecycle:
    async def test_a_base_url_str_builds_and_closes_its_client(self) -> None:
        """A str base_url makes the client own and close its AsyncClient."""
        client = PIIGhostClient("http://api")
        assert client._owns_client is True
        await client.aclose()
        assert client._client.is_closed is True

    async def test_an_injected_client_is_not_closed(self) -> None:
        """An injected AsyncClient is left open, it belongs to the caller."""
        transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
        http = httpx.AsyncClient(transport=transport, base_url="http://api")
        client = PIIGhostClient(http)
        await client.aclose()
        assert http.is_closed is False
        await http.aclose()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/integrations/client/test_client.py -q`
Expected: FAIL with `ImportError` on `piighost.integrations.client` / `RemoteError`.

- [ ] **Step 3: Add the exceptions and the client**

In `src/piighost/exceptions.py`, at the end of the file, add:

```python
class ClientError(PIIGhostError):
    """Base class for errors raised by the remote client.

    Catch this to handle any client failure at once, or catch one of its
    subclasses to react to a specific violation.
    """


class RemoteError(ClientError):
    """Raised when the remote piighost-api returns a non-2xx response.

    Attributes:
        status_code: The HTTP status the server returned.
    """

    def __init__(self, message: str, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(message)
```

Create `src/piighost/integrations/client/remote.py`:

```python
"""Remote thread pipeline client over HTTP (optional: client).

PIIGhostClient is a remote stand-in for a ThreadAnonymizationPipeline: it
implements the same AnyThreadPipeline port by calling piighost-api. This module
needs the httpx package; it is guarded so importing it without the dependency
raises an ImportError pointing at the extra.
"""

import importlib.util
from typing import Self

from piighost.components.anonymizer.base import Anonymization
from piighost.components.placeholder.base import BaseDelimitedPlaceholderFactory
from piighost.components.placeholder.label_counter import (
    LabelCounterPlaceholderFactory,
)
from piighost.components.placeholder.tags import PreservesRecognizableIdentity
from piighost.conversation_memory.base import Forgotten, MessageRole
from piighost.exceptions import RemoteError
from piighost.models import Detection

if importlib.util.find_spec("httpx") is None:
    raise ImportError(
        "PIIGhostClient requires the httpx package. "
        "Install it with: pip install piighost[client]"
    )

import httpx  # noqa: E402


class PIIGhostClient:
    """A remote thread pipeline, calling piighost-api over HTTP.

    It implements the AnyThreadPipeline port so a caller, such as the
    middleware, drives a remote pipeline exactly like a local one. The server
    owns the token mapping, so anonymize returns an Anonymization with empty
    tokens and deanonymize restores through the server. The token grammar is
    declared by the recognizer, defaulting to the standard delimited grammar a
    piighost server emits, overridable when the server is configured otherwise.

    Attributes:
        recognizer: The grammar of the tokens the server emits.
    """

    def __init__(
        self,
        client: "httpx.AsyncClient | str",
        recognizer: BaseDelimitedPlaceholderFactory | None = None,
    ) -> None:
        """Store or build the HTTP client and the token recognizer.

        A str is a base URL: the client builds and owns its AsyncClient, closed
        by aclose or the context manager. An injected AsyncClient is used as-is
        and never closed here, it belongs to the caller.
        """
        if isinstance(client, str):
            self._client = httpx.AsyncClient(base_url=client)
            self._owns_client = True
        else:
            self._client = client
            self._owns_client = False
        self._recognizer = recognizer or LabelCounterPlaceholderFactory()

    @property
    def recognizer(self) -> BaseDelimitedPlaceholderFactory | None:
        """The grammar of the tokens the server emits."""
        return self._recognizer

    async def anonymize(
        self, text: str, thread_id: str, role: MessageRole = MessageRole.USER
    ) -> Anonymization[PreservesRecognizableIdentity]:
        """Anonymize a message remotely, returning empty-token Anonymization."""
        payload = {"text": text, "thread_id": thread_id, "role": role.value}
        data = await self._post("/v1/anonymize", payload)
        return Anonymization(text=data["anonymized_text"], tokens={})

    async def anonymize_corrected(
        self, text: str, thread_id: str, detections: list[Detection]
    ) -> Anonymization[PreservesRecognizableIdentity]:
        """Re-anonymize a user message remotely with a corrected detection set."""
        payload = {
            "text": text,
            "thread_id": thread_id,
            "detections": [detection.to_dict() for detection in detections],
        }
        data = await self._post("/v1/anonymize/corrected", payload)
        return Anonymization(text=data["anonymized_text"], tokens={})

    async def deanonymize(self, text: str, thread_id: str) -> str:
        """Deanonymize text remotely through the server's thread mapping."""
        data = await self._post(
            "/v1/deanonymize", {"text": text, "thread_id": thread_id}
        )
        return data["text"]

    async def forget_thread(self, thread_id: str) -> Forgotten:
        """Erase a thread server-side and report what was dropped."""
        response = await self._client.delete(f"/v1/threads/{thread_id}")
        data = self._json(response)
        return Forgotten(messages=data["messages"], detections=data["detections"])

    async def aclose(self) -> None:
        """Close the underlying client when this one built it."""
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> Self:
        """Enter the async context, returning the client."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Close the client on context exit."""
        await self.aclose()

    async def _post(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        """POST a JSON payload and return the parsed body, raising on non-2xx."""
        response = await self._client.post(path, json=payload)
        return self._json(response)

    def _json(self, response: "httpx.Response") -> dict[str, object]:
        """Return a response's JSON body, raising RemoteError on a non-2xx."""
        if response.is_success:
            return response.json()
        raise RemoteError(
            f"piighost-api returned {response.status_code}: {response.text}",
            response.status_code,
        )
```

Create `src/piighost/integrations/client/__init__.py`:

```python
"""Remote client for piighost-api.

PIIGhostClient needs the httpx optional dependency, so it is imported lazily:
reaching for it without the extra raises a helpful ImportError, while importing
this package never pulls httpx in.
"""

from typing import Any

__all__ = ["PIIGhostClient"]


def __getattr__(name: str) -> Any:
    """Import PIIGhostClient on demand so its optional dependency stays optional."""
    if name == "PIIGhostClient":
        from piighost.integrations.client.remote import PIIGhostClient

        return PIIGhostClient

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

Note on the `forget_thread` URL: httpx percent-encodes the path when it builds the request, so a space in the thread id becomes `%20` and the `test_deletes_and_returns_a_forgotten` test sees `/v1/threads/t%201`. Confirm this in Step 4; if httpx leaves the space raw, wrap the id with `urllib.parse.quote(thread_id, safe="")` and keep the test's expectation.

- [ ] **Step 4: Run the client tests**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/integrations/client/test_client.py -q`
Expected: PASS. If the URL-quoting assertion fails, switch to `urllib.parse.quote` as noted and re-run.

- [ ] **Step 5: Lint, types, commit**

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean, pyrefly 0 errors. If pyrefly rejects `Anonymization(text=..., tokens={})` against the `PreservesRecognizableIdentity` return annotation, report it (do not suppress); the empty dict should unify.

```bash
git add src/piighost/exceptions.py src/piighost/integrations/client tests/integrations/client/test_client.py
git commit -m "feat(client): add the remote thread pipeline client"
```

---

### Task 4: Public-API regression and full verification

**Files:**
- Modify: `tests/regression/test_imports.py`

- [ ] **Step 1: Add the new symbols to the regression guard**

In `tests/regression/test_imports.py`, in `PUBLIC_API`, after the `("piighost.pipeline", "ThreadAnonymizationPipeline"),` line add:

```python
    ("piighost.pipeline", "AnyThreadPipeline"),
```

and after the `("piighost.exceptions", "ConflictingOverrideError"),` line add:

```python
    ("piighost.exceptions", "ClientError"),
    ("piighost.exceptions", "RemoteError"),
```

Do NOT add `PIIGhostClient` (lazy behind the `client` extra; the walk covers `integrations/client/remote.py`).

- [ ] **Step 2: Run the regression guard, the full suite, and the checks**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/regression/test_imports.py -q`
Expected: PASS with the three new cases.

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest -q`
Expected: PASS.

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean, pyrefly 0 errors.

- [ ] **Step 3: Commit**

```bash
git add tests/regression/test_imports.py
git commit -m "test(client): guard the thread port and client exception symbols"
```

---

## Notes for the implementer

- The whole point is that the middleware no longer knows local from remote: it types on `AnyThreadPipeline` and reads `recognizer`. Do not reintroduce any `pipeline.anonymizer` access in the middleware.
- The remote `anonymize`/`anonymize_corrected` return `Anonymization` with empty tokens by design; the server owns the mapping and `deanonymize` (a plain str) restores. Do not try to reconstruct the token mapping over the wire.
- The client closes its `AsyncClient` ONLY when it built it from a str base URL (`_owns_client`); an injected client belongs to the caller.
- `client` extra is already declared in `pyproject.toml` (`httpx`), and httpx is in the dev venv, so the client tests run for real via `httpx.MockTransport`; no `importorskip` is needed.
- No pyrefly suppression is expected. If the empty-token `Anonymization` typing or the httpx types fight pyrefly, report the exact message rather than suppressing.
