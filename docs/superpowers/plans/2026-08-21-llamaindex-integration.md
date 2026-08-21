# LlamaIndex Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep PII out of both the embedding and the generation calls of a LlamaIndex RAG pipeline, via an ingestion-time node transform and a query-engine wrapper.

**Architecture:** `PIINodeAnonymizer` (a `TransformComponent`) anonymizes node text before embedding; `PIIQueryEngine` (a `BaseQueryEngine` wrapper) anonymizes the query before retrieval and deanonymizes the answer. Both take an `AnyThreadPipeline` and a shared `thread_id`; the transform calls `pipeline.anonymize` directly, the query engine uses the shared `TextDeidentifier` for the invented-placeholder policy on restore. Behind a new `llama-index` optional extra.

**Tech Stack:** Python 3.11+, llama-index-core, pydantic v2, pytest (asyncio auto mode), uv, ruff, pyrefly, bandit.

**Spec:** `docs/superpowers/specs/2026-08-21-llamaindex-integration-design.md`

---

## File Structure

- `pyproject.toml` — add the `llama-index` optional extra, dependency-group, and to `all`.
- `src/piighost/integrations/llama_index/__init__.py` (create) — lazy exports.
- `src/piighost/integrations/llama_index/transform.py` (create) — `PIINodeAnonymizer`.
- `src/piighost/integrations/llama_index/query_engine.py` (create) — `PIIQueryEngine`.
- `tests/integrations/llama_index/test_transform.py` (create).
- `tests/integrations/llama_index/test_query_engine.py` (create).
- `examples/llama_index/rag.py` (create) — runnable PEP 723 demo.
- `docs/en/examples/llama-index.md`, `docs/fr/examples/llama-index.md` (create) + nav in `zensical.toml`, `zensical.fr.toml`.
- `docs/en/roadmap.md`, `docs/fr/roadmap.md` (modify) — drop the shipped item.

Run integration tests with the extra: `uv run --group llama-index pytest <path>`. The default `uv run pytest` skips them via `importorskip`.

---

## Task 1: Add the `llama-index` optional extra and dependency-group

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the optional extra**

Under `[project.optional-dependencies]`, add after the `presidio` block:

```toml
llama-index = [
    "llama-index-core>=0.14",
]
```

- [ ] **Step 2: Add to the `all` extra**

Append `llama-index` to the `all` inclusion list so it ends with `,presidio,llama-index]`:

```toml
all = [
    "piighost[gliner2,redis,middleware,pydantic-ai,client,spacy,transformers,llm,observation,fuzzy,config,argon2,crypto,mistral,sqlalchemy,presidio,llama-index]",
]
```

- [ ] **Step 3: Add the dependency-group**

Under `[dependency-groups]`, add after the `presidio` group:

```toml
llama-index = [
    "llama-index-core>=0.14",
]
```

- [ ] **Step 4: Update the lockfile**

Run: `uv lock`
Expected: `uv.lock` is rewritten with `llama-index-core` and its transitive deps.

- [ ] **Step 5: Verify the group installs and imports**

Run: `uv run --group llama-index python -c "import llama_index; from llama_index.core.schema import TransformComponent; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add the llama-index optional extra"
```

---

## Task 2: `PIINodeAnonymizer` transform

**Files:**
- Create: `src/piighost/integrations/llama_index/__init__.py`
- Create: `src/piighost/integrations/llama_index/transform.py`
- Test: `tests/integrations/llama_index/test_transform.py`

- [ ] **Step 1: Write the failing test**

Create `tests/integrations/llama_index/test_transform.py`:

```python
"""Tests for the LlamaIndex node anonymizer transform.

An ExactMatchDetector over an in-memory thread pipeline keeps a value's token
stable across nodes, so no model loads and no network call is made; they skip
when llama-index is absent.
"""

import pytest

pytest.importorskip("llama_index")

from llama_index.core.schema import TextNode  # noqa: E402

from piighost.components.detector import ExactMatchDetector  # noqa: E402
from piighost.integrations.llama_index import PIINodeAnonymizer  # noqa: E402
from piighost.pipeline import ThreadAnonymizationPipeline  # noqa: E402


def _pipeline() -> ThreadAnonymizationPipeline:
    detector = ExactMatchDetector({"Emma": "PERSON", "Paris": "LOCATION"})
    return ThreadAnonymizationPipeline(detector)


async def test_anonymizes_each_node_text() -> None:
    """Each node's text is replaced with its anonymized form."""
    transform = PIINodeAnonymizer(pipeline=_pipeline(), thread_id="corpus")
    nodes = [TextNode(text="Emma lives in Paris")]
    result = await transform.acall(nodes)
    assert result[0].text == "<<PERSON:1>> lives in <<LOCATION:1>>"


async def test_keeps_one_token_per_value_across_nodes() -> None:
    """A value repeated across nodes keeps the same token within the thread."""
    transform = PIINodeAnonymizer(pipeline=_pipeline(), thread_id="corpus")
    nodes = [TextNode(text="Emma lives in Paris"), TextNode(text="Emma works")]
    result = await transform.acall(nodes)
    assert result[0].text == "<<PERSON:1>> lives in <<LOCATION:1>>"
    assert result[1].text == "<<PERSON:1>> works"


def test_sync_call_bridges_to_acall() -> None:
    """The sync __call__ path anonymizes the nodes too."""
    transform = PIINodeAnonymizer(pipeline=_pipeline(), thread_id="corpus")
    nodes = [TextNode(text="Emma works")]
    result = transform(nodes)
    assert result[0].text == "<<PERSON:1>> works"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --group llama-index pytest tests/integrations/llama_index/test_transform.py -v`
Expected: FAIL importing `PIINodeAnonymizer` (module does not exist yet).

- [ ] **Step 3: Create the transform**

Create `src/piighost/integrations/llama_index/transform.py`:

```python
"""LlamaIndex ingestion transform that anonymizes node text (optional: llama-index).

A TransformComponent that anonymizes each node's text before it is embedded, so
the embedding provider never sees PII. It calls the thread pipeline's anonymize
directly, since ingestion only anonymizes and never restores. This module needs
the llama-index package; it is guarded so importing it without the dependency
raises an ImportError pointing at the extra.
"""

import asyncio
import importlib.util
from typing import Any

from pydantic import ConfigDict

from piighost.pipeline import AnyThreadPipeline

if importlib.util.find_spec("llama_index") is None:
    raise ImportError(
        "The LlamaIndex integration requires the llama-index package. "
        "Install it with: pip install piighost[llama-index]"
    )

from llama_index.core.schema import TransformComponent  # pyrefly: ignore[missing-import]  # noqa: E402


class PIINodeAnonymizer(TransformComponent):
    """Anonymize each node's text within a corpus thread before embedding.

    Placed in an index or ingestion pipeline's transformations before the
    embedding model, so the index is built on anonymized text and no PII reaches
    the embedding provider. A value keeps one token across the corpus because
    every node is anonymized into the same thread.

    Attributes:
        pipeline: The thread pipeline that detects and tokenizes.
        thread_id: The corpus thread every node is anonymized into.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    pipeline: AnyThreadPipeline
    thread_id: str

    def __call__(self, nodes: Any, **kwargs: Any) -> Any:
        """Run the async anonymization from LlamaIndex's sync ingestion path."""
        return asyncio.run(self.acall(nodes, **kwargs))

    async def acall(self, nodes: Any, **kwargs: Any) -> Any:
        """Replace each node's text with its anonymized form in the thread."""
        for node in nodes:
            result = await self.pipeline.anonymize(node.text, self.thread_id)
            node.text = result.text
        return nodes
```

- [ ] **Step 4: Create the package init with a lazy export**

Create `src/piighost/integrations/llama_index/__init__.py`:

```python
"""LlamaIndex integration for PII de-identification in a RAG pipeline.

Needs the llama-index optional dependency (pip install piighost[llama-index]), so
its modules are imported lazily: reaching for a component without the extra raises
a helpful ImportError, while importing this package never pulls llama-index in.
"""

from typing import Any

__all__ = ["PIINodeAnonymizer"]


def __getattr__(name: str) -> Any:
    """Import a component on demand so the optional dependency stays optional."""
    if name == "PIINodeAnonymizer":
        from piighost.integrations.llama_index.transform import PIINodeAnonymizer

        return PIINodeAnonymizer

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run --group llama-index pytest tests/integrations/llama_index/test_transform.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Lint**

Run: `make lint`
Expected: passes (llama-index absent in the default env, so pyrefly does not type-check the guarded import).

- [ ] **Step 7: Commit**

```bash
git add src/piighost/integrations/llama_index/__init__.py src/piighost/integrations/llama_index/transform.py tests/integrations/llama_index/test_transform.py
git commit -m "feat(llama-index): add the PIINodeAnonymizer ingestion transform"
```

---

## Task 3: `PIIQueryEngine` wrapper

**Files:**
- Create: `src/piighost/integrations/llama_index/query_engine.py`
- Modify: `src/piighost/integrations/llama_index/__init__.py`
- Test: `tests/integrations/llama_index/test_query_engine.py`

- [ ] **Step 1: Write the failing test**

Create `tests/integrations/llama_index/test_query_engine.py`:

```python
"""Tests for the LlamaIndex query-engine wrapper.

A fake inner engine and an ExactMatchDetector thread pipeline keep everything
offline; they skip when llama-index is absent.
"""

import pytest

pytest.importorskip("llama_index")

from piighost.components.detector import ExactMatchDetector  # noqa: E402
from piighost.integrations.llama_index import PIIQueryEngine  # noqa: E402
from piighost.pipeline import ThreadAnonymizationPipeline  # noqa: E402


class _FakeResponse:
    """A stand-in for a LlamaIndex Response with a mutable response string."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.source_nodes: list[object] = []


class _FakeInner:
    """A stand-in query engine recording the query it received."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.received: str | None = None

    async def aquery(self, query: str) -> _FakeResponse:
        self.received = query
        return _FakeResponse(self._response)

    def query(self, query: str) -> _FakeResponse:
        self.received = query
        return _FakeResponse(self._response)


def _pipeline() -> ThreadAnonymizationPipeline:
    detector = ExactMatchDetector({"Emma": "PERSON"})
    return ThreadAnonymizationPipeline(detector)


async def test_anonymizes_query_and_restores_answer() -> None:
    """The inner engine sees the anonymized query; the answer is restored."""
    from llama_index.core.schema import QueryBundle

    inner = _FakeInner("<<PERSON:1>> is in the office")
    engine = PIIQueryEngine(inner=inner, pipeline=_pipeline(), thread_id="t")
    response = await engine._aquery(QueryBundle(query_str="Where is Emma?"))
    assert inner.received == "Where is <<PERSON:1>>?"
    assert response.response == "Emma is in the office"


def test_sync_query_bridges_to_aquery() -> None:
    """The public sync query path anonymizes and restores too."""
    inner = _FakeInner("<<PERSON:1>> is here")
    engine = PIIQueryEngine(inner=inner, pipeline=_pipeline(), thread_id="t")
    response = engine.query("Where is Emma?")
    assert inner.received == "Where is <<PERSON:1>>?"
    assert response.response == "Emma is here"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --group llama-index pytest tests/integrations/llama_index/test_query_engine.py -v`
Expected: FAIL importing `PIIQueryEngine`.

- [ ] **Step 3: Create the query-engine wrapper**

Create `src/piighost/integrations/llama_index/query_engine.py`.

Note on the base import: `BaseQueryEngine` lives at `llama_index.core.base.base_query_engine`. If that import fails at runtime, use the alternative `from llama_index.core.query_engine import BaseQueryEngine` and keep the rest unchanged.

```python
"""LlamaIndex query-engine wrapper that de-identifies a RAG query (optional: llama-index).

Wraps any query engine: it anonymizes the query into the corpus thread so
retrieval matches the anonymized index, delegates to the inner engine, and
deanonymizes the answer through the shared TextDeidentifier so the caller sees
real values while the model only ever saw tokens. This module needs the
llama-index package; it is guarded so importing it without the dependency raises
an ImportError pointing at the extra.
"""

import asyncio
import importlib.util
from typing import Any

from piighost.integrations._deidentify import TextDeidentifier
from piighost.integrations.middleware.strategy import InventedPlaceholderStrategy
from piighost.pipeline import AnyThreadPipeline

if importlib.util.find_spec("llama_index") is None:
    raise ImportError(
        "The LlamaIndex integration requires the llama-index package. "
        "Install it with: pip install piighost[llama-index]"
    )

from llama_index.core.base.base_query_engine import (  # pyrefly: ignore[missing-import]  # noqa: E402
    BaseQueryEngine,
)


class PIIQueryEngine(BaseQueryEngine):
    """Anonymize a RAG query and restore the answer around any inner engine.

    Attributes:
        invented_strategy: How a token the pipeline never issued is handled when
            restoring the answer, KEEP, DROP, or RAISE.
    """

    def __init__(
        self,
        inner: Any,
        pipeline: AnyThreadPipeline,
        thread_id: str,
        invented_strategy: InventedPlaceholderStrategy = InventedPlaceholderStrategy.RAISE,
        callback_manager: Any = None,
    ) -> None:
        """Wrap the inner engine and build the shared de-identifier."""
        super().__init__(callback_manager)
        self._inner = inner
        self._deidentifier = TextDeidentifier(pipeline, invented_strategy)
        self._thread_id = thread_id
        self.invented_strategy = invented_strategy

    async def _aquery(self, query_bundle: Any) -> Any:
        """Anonymize the query, delegate, then deanonymize the answer."""
        anonymized = await self._deidentifier.anonymize(
            query_bundle.query_str, self._thread_id
        )
        response = await self._inner.aquery(anonymized)
        if response.response is not None:
            response.response = await self._deidentifier.deanonymize(
                response.response, self._thread_id
            )
        return response

    def _query(self, query_bundle: Any) -> Any:
        """Run the async query from LlamaIndex's sync query path."""
        return asyncio.run(self._aquery(query_bundle))

    def _get_prompt_modules(self) -> dict[str, Any]:
        """No prompt modules: this engine only wraps another one."""
        return {}
```

- [ ] **Step 4: Add the lazy export**

In `src/piighost/integrations/llama_index/__init__.py`, add `"PIIQueryEngine"` to `__all__` (after `"PIINodeAnonymizer"`):

```python
__all__ = ["PIINodeAnonymizer", "PIIQueryEngine"]
```

And add a `__getattr__` branch after the `PIINodeAnonymizer` branch:

```python
    if name == "PIIQueryEngine":
        from piighost.integrations.llama_index.query_engine import PIIQueryEngine

        return PIIQueryEngine
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run --group llama-index pytest tests/integrations/llama_index/test_query_engine.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Run the full default suite and lint**

Run: `uv run pytest -q && make lint`
Expected: all pass; the llama-index tests skip in the default env.

- [ ] **Step 7: Commit**

```bash
git add src/piighost/integrations/llama_index/query_engine.py src/piighost/integrations/llama_index/__init__.py tests/integrations/llama_index/test_query_engine.py
git commit -m "feat(llama-index): add the PIIQueryEngine wrapper"
```

---

## Task 4: Runnable example

**Files:**
- Create: `examples/llama_index/rag.py`

- [ ] **Step 1: Create the example**

Create `examples/llama_index/rag.py`:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "piighost[llama-index]",
#     "llama-index-embeddings-openai>=0.3",
#     "llama-index-llms-openai>=0.3",
#     "python-dotenv>=1.0",
# ]
#
# [tool.uv.sources]
# piighost = { path = "../..", editable = true }
# ///
"""Retrieval-augmented generation in LlamaIndex where OpenAI never sees the PII.

A minimalist RAG over a tiny corpus, showing the two piighost LlamaIndex
components. PIINodeAnonymizer anonymizes each document into one corpus thread
before it is embedded, so the embedding provider only ever sees tokens.
PIIQueryEngine anonymizes the query into the same thread, so its tokens match the
corpus and retrieval works, then deanonymizes the answer for the user. OpenAI only
ever handled tokens like <<PERSON:1>>, never Patrick or Paris.

An ExactMatchDetector keeps the demo deterministic. It runs against OpenAI
embeddings and gpt-5.5, so set an OPENAI_API_KEY in the environment (copy
.env.example to .env). Run with:
uv run examples/llama_index/rag.py
"""

from dotenv import load_dotenv
from llama_index.core import Document, Settings, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding  # pyrefly: ignore[missing-import]
from llama_index.llms.openai import OpenAI  # pyrefly: ignore[missing-import]

from piighost.components.detector import ExactMatchDetector
from piighost.integrations.llama_index import PIINodeAnonymizer, PIIQueryEngine
from piighost.pipeline import ThreadAnonymizationPipeline

THREAD = "docs"

CORPUS = [
    "Patrick manages the Lyon office and lives in Paris.",
    "Marie is the contact for the Berlin branch.",
    "The Paris office handles European support.",
]


def main() -> None:
    """Index an anonymized corpus, answer a query, and restore the reply."""
    load_dotenv()
    labels = {
        "Patrick": "PERSON",
        "Marie": "PERSON",
        "Paris": "LOCATION",
        "Lyon": "LOCATION",
        "Berlin": "LOCATION",
    }
    detector = ExactMatchDetector(labels)
    pipeline = ThreadAnonymizationPipeline(detector)

    Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")
    Settings.llm = OpenAI(model="gpt-5.5")

    # Ingest: the anonymizer runs before embedding, so the embedding provider
    # only ever sees tokens, and a value keeps one token across the corpus.
    anonymizer = PIINodeAnonymizer(pipeline=pipeline, thread_id=THREAD)
    documents = [Document(text=text) for text in CORPUS]
    index = VectorStoreIndex.from_documents(
        documents,
        transformations=[SentenceSplitter(), anonymizer],
    )

    # Query: the wrapper anonymizes the question into the same thread, so its
    # tokens match the corpus, and restores the answer for the user.
    engine = PIIQueryEngine(
        inner=index.as_query_engine(),
        pipeline=pipeline,
        thread_id=THREAD,
    )
    answer = engine.query("Where does Patrick live?")

    print("== what the user sees (restored) ==")
    print(f"  {answer.response!r}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Byte-compile and lint the example**

Run: `uv run python -m py_compile examples/llama_index/rag.py && uv run ruff check examples/llama_index/rag.py && uv run ruff format --check examples/llama_index/rag.py`
Expected: no errors (the example is checked by the same ruff config as the rest of the repo).

- [ ] **Step 3: Commit**

```bash
git add examples/llama_index/rag.py
git commit -m "docs(examples): add a minimal LlamaIndex RAG example with anonymization"
```

Note: running the example end to end needs an `OPENAI_API_KEY` and network plus the two OpenAI integration packages; the controller verifies it out of band, as with `examples/langchain/rag.py`.

---

## Task 5: Documentation and roadmap

**Files:**
- Create: `docs/en/examples/llama-index.md`, `docs/fr/examples/llama-index.md`
- Modify: `zensical.toml`, `zensical.fr.toml`, `docs/en/roadmap.md`, `docs/fr/roadmap.md`

- [ ] **Step 1: Write the EN example page**

Create `docs/en/examples/llama-index.md`:

````markdown
---
icon: lucide/link
---

# Keep PII out of a LlamaIndex RAG pipeline

You want a LlamaIndex RAG where neither the embedding provider nor the LLM ever sees PII. `piighost` gives you two components: `PIINodeAnonymizer`, an ingestion transform that anonymizes each node before it is embedded, and `PIIQueryEngine`, a wrapper that anonymizes the query and restores the answer. Both share one thread pipeline, so a value keeps the same token across the corpus and the query.

For the by-hand version without the components, see the [LangChain RAG example](langchain.md); this page packages the same idea as reusable LlamaIndex objects.

!!! note "Prerequisites"
    `piighost` installed with the llama-index extra, `pip install piighost[llama-index]`, plus `llama-index-embeddings-openai` and `llama-index-llms-openai` and an `OPENAI_API_KEY`.

## 1. Build the thread pipeline

The pipeline anonymizes and restores over a corpus thread. Here an `ExactMatchDetector` keeps the example deterministic; swap in a model detector for real text.

```python
from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import ThreadAnonymizationPipeline

THREAD = "docs"
detector = ExactMatchDetector({"Patrick": "PERSON", "Paris": "LOCATION"})
pipeline = ThreadAnonymizationPipeline(detector)
```

## 2. Anonymize at ingestion, before embedding

Put `PIINodeAnonymizer` in the transformations before the embedding model, so the index is built on tokens and the embedding provider never sees PII.

```python
from llama_index.core import Document, Settings, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding

from piighost.integrations.llama_index import PIINodeAnonymizer

Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")
anonymizer = PIINodeAnonymizer(pipeline=pipeline, thread_id=THREAD)
index = VectorStoreIndex.from_documents(
    [Document(text="Patrick lives in Paris.")],
    transformations=[SentenceSplitter(), anonymizer],
)
```

## 3. Wrap the query engine

`PIIQueryEngine` anonymizes the query into the same thread, so retrieval matches the anonymized corpus, and deanonymizes the answer for the user.

```python
from llama_index.llms.openai import OpenAI

from piighost.integrations.llama_index import PIIQueryEngine

Settings.llm = OpenAI(model="gpt-5.5")
engine = PIIQueryEngine(
    inner=index.as_query_engine(),
    pipeline=pipeline,
    thread_id=THREAD,
)
answer = engine.query("Where does Patrick live?")
print(answer.response)
```

The LLM answered over `<<PERSON:1>>`{ .placeholder } and `<<LOCATION:1>>`{ .placeholder }; the user sees `Patrick`{ .pii } and `Paris`{ .pii } restored. Retrieval runs on the anonymized space, which trades some quality for keeping PII out of the embedding call.

## See also

- [LangChain RAG example](langchain.md): the same idea orchestrated by hand.
- [Roadmap](../roadmap.md): what else is planned.
````

- [ ] **Step 2: Write the FR example page**

Create `docs/fr/examples/llama-index.md`. Translate the prose to French with correct accents; keep every fenced code block byte-identical to the EN page.

````markdown
---
icon: lucide/link
---

# Garder les PII hors d'un pipeline RAG LlamaIndex

Vous voulez un RAG LlamaIndex où ni le fournisseur d'embeddings ni le LLM ne voient de PII. `piighost` fournit deux composants : `PIINodeAnonymizer`, un transform d'ingestion qui anonymise chaque node avant l'embedding, et `PIIQueryEngine`, un wrapper qui anonymise la requête et restaure la réponse. Les deux partagent un pipeline de thread, donc une valeur garde le même token à travers le corpus et la requête.

Pour la version à la main sans les composants, voir l'[exemple RAG LangChain](langchain.md) ; cette page emballe la même idée en objets LlamaIndex réutilisables.

!!! note "Prérequis"
    `piighost` installé avec l'extra llama-index, `pip install piighost[llama-index]`, plus `llama-index-embeddings-openai` et `llama-index-llms-openai` et un `OPENAI_API_KEY`.

## 1. Construire le pipeline de thread

Le pipeline anonymise et restaure sur un thread corpus. Ici un `ExactMatchDetector` garde l'exemple déterministe ; remplacez-le par un détecteur à modèle pour du vrai texte.

```python
from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import ThreadAnonymizationPipeline

THREAD = "docs"
detector = ExactMatchDetector({"Patrick": "PERSON", "Paris": "LOCATION"})
pipeline = ThreadAnonymizationPipeline(detector)
```

## 2. Anonymiser à l'ingestion, avant l'embedding

Placez `PIINodeAnonymizer` dans les transformations avant le modèle d'embedding, pour que l'index soit bâti sur des tokens et que le fournisseur d'embeddings ne voie jamais de PII.

```python
from llama_index.core import Document, Settings, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding

from piighost.integrations.llama_index import PIINodeAnonymizer

Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")
anonymizer = PIINodeAnonymizer(pipeline=pipeline, thread_id=THREAD)
index = VectorStoreIndex.from_documents(
    [Document(text="Patrick lives in Paris.")],
    transformations=[SentenceSplitter(), anonymizer],
)
```

## 3. Envelopper le query engine

`PIIQueryEngine` anonymise la requête dans le même thread, donc le retrieval concorde avec le corpus anonymisé, et désanonymise la réponse pour l'utilisateur.

```python
from llama_index.llms.openai import OpenAI

from piighost.integrations.llama_index import PIIQueryEngine

Settings.llm = OpenAI(model="gpt-5.5")
engine = PIIQueryEngine(
    inner=index.as_query_engine(),
    pipeline=pipeline,
    thread_id=THREAD,
)
answer = engine.query("Where does Patrick live?")
print(answer.response)
```

Le LLM a répondu sur `<<PERSON:1>>`{ .placeholder } et `<<LOCATION:1>>`{ .placeholder } ; l'utilisateur voit `Patrick`{ .pii } et `Paris`{ .pii } restaurés. Le retrieval tourne sur l'espace anonymisé, ce qui échange un peu de qualité contre le fait de garder les PII hors de l'appel d'embedding.

## Voir aussi

- [Exemple RAG LangChain](langchain.md) : la même idée orchestrée à la main.
- [Roadmap](../roadmap.md) : ce qui est prévu par ailleurs.
````

- [ ] **Step 3: Add the nav entries**

In `zensical.toml`, after the `{ "Pydantic AI integration" = "examples/pydantic-ai.md" },` line, add:

```toml
    { "LlamaIndex integration" = "examples/llama-index.md" },
```

In `zensical.fr.toml`, after the `{ "Intégration Pydantic AI" = "examples/pydantic-ai.md" },` line, add:

```toml
        { "Intégration LlamaIndex" = "examples/llama-index.md" },
```

- [ ] **Step 4: Drop the shipped roadmap item (EN)**

In `docs/en/roadmap.md`, delete the entire `## LlamaIndex integration` section (heading and its paragraph), leaving no double blank line.

- [ ] **Step 5: Drop the shipped roadmap item (FR)**

In `docs/fr/roadmap.md`, delete the entire `## Intégration LlamaIndex` section (heading and its paragraph), leaving no double blank line.

- [ ] **Step 6: Build both docs**

Run:
```bash
uv run zensical build --clean
uv run zensical build -f zensical.fr.toml
```
Expected: both succeed with no broken-link errors.

- [ ] **Step 7: Commit**

```bash
git add docs/en/examples/llama-index.md docs/fr/examples/llama-index.md zensical.toml zensical.fr.toml docs/en/roadmap.md docs/fr/roadmap.md
git commit -m "docs(llama-index): document the LlamaIndex RAG integration (EN+FR)"
```

---

## Self-Review

**Spec coverage:**
- Ingestion transform anonymizing before embedding → Task 2 (`PIINodeAnonymizer`). ✓
- Query-engine wrapper anonymizing the query and restoring the answer → Task 3 (`PIIQueryEngine`). ✓
- Shared pipeline + thread for token consistency → both components take `pipeline` + `thread_id`; the example and docs pass one pipeline to both. ✓ (Plan refinement over the spec: components take a pipeline, not a pre-built `TextDeidentifier`, matching the middleware; the transform calls `pipeline.anonymize` directly since it never restores, the query engine builds a `TextDeidentifier` for the invented policy.)
- `llama-index` extra + guarded modules + lazy exposure → Tasks 1, 2, 3. ✓
- Error handling (guard naming the extra; `piighost[` substring) → Tasks 2, 3 module guards; regression import test auto-covers. ✓
- Testing (offline, ExactMatch + fakes) → Tasks 2, 3. ✓
- Example → Task 4. ✓
- Docs (example page EN+FR + nav) and roadmap removal → Task 5. ✓
- `response.response is None` guard → Task 3 `_aquery`. ✓
- source_nodes stay anonymized (out of scope) → not restored anywhere. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code. The `BaseQueryEngine` import has a concrete primary path plus a one-line fallback instruction, not a placeholder.

**Type consistency:** `PIINodeAnonymizer(pipeline, thread_id)` and `PIIQueryEngine(inner, pipeline, thread_id, invented_strategy, callback_manager)` are identical across Tasks 2, 3, 4, and the docs. `acall`/`__call__` and `_aquery`/`_query`/`_get_prompt_modules` match between the classes and their tests. `node.text`, `query_bundle.query_str`, and `response.response` match the LlamaIndex shapes verified via context7. Both components import `AnyThreadPipeline` from `piighost.pipeline`.
