# LlamaIndex integration: design

**Date:** 2026-08-21
**Status:** approved
**Roadmap item:** "LlamaIndex integration" (docs/en|fr/roadmap.md)

## Goal

Let a LlamaIndex RAG pipeline keep PII out of both the embedding and the
generation calls, using piighost's conversation pipeline. Documents are
anonymized before they are embedded, the query is anonymized before retrieval so
its tokens match the corpus, the LLM answers over anonymized context, and the
answer is deanonymized for the user. This mirrors what `examples/langchain/rag.py`
does by hand, packaged as two reusable LlamaIndex components.

## Scope

- The embedding provider must never see PII, so anonymization happens at
  ingestion (before embedding), not after retrieval. A `NodePostprocessor` runs
  after retrieval and is therefore the wrong hook; it is not used.
- Two components, both programmatic (no config model, matching the middleware):
  an ingestion-time node transform and a query-engine wrapper.
- Both are constructed by the caller with the SAME `TextDeidentifier` and the
  SAME `thread_id`. The token-to-value map lives in the conversation memory keyed
  by thread, so ingestion and query must share it, or the query tokens will not
  match the corpus and restoration will fail. With a durable memory backend
  (SqlAlchemy or Redis) the two can run in separate processes over the shared
  backend.
- Retrieval runs on the anonymized space. This trades some retrieval quality for
  privacy, the same tradeoff the by-hand example makes.

## Approach

Reuse `TextDeidentifier` (`src/piighost/integrations/_deidentify.py`), the
framework-agnostic core already shared by the LangChain middleware and the
Pydantic AI hooks. It wraps an `AnyThreadPipeline` and exposes async
`anonymize(text, thread_id, role)` and `deanonymize(text, thread_id)` with the
invented-placeholder policy. The two LlamaIndex components hold a
`TextDeidentifier` and a `thread_id` and call into it.

Verified LlamaIndex extension points (v0.14.x):

- `llama_index.core.schema.TransformComponent`: subclass and implement
  `__call__(self, nodes, **kwargs)` (and async `acall`) that mutates `node.text`
  and returns the nodes. It is a pydantic model, so an injected non-pydantic
  object needs `model_config = ConfigDict(arbitrary_types_allowed=True)`.
- `llama_index.core.base.base_query_engine.BaseQueryEngine`: a plain class (not
  pydantic) taking a `callback_manager`; subclass and implement
  `_query(self, query_bundle) -> RESPONSE_TYPE`, `_aquery`, and
  `_get_prompt_modules() -> dict`. `FLAREInstructQueryEngine` is the in-tree
  precedent for a query engine that wraps an inner engine.

## Components

### 1. `PIINodeAnonymizer(TransformComponent)`

An ingestion-time transform that anonymizes node text before embedding.

```python
class PIINodeAnonymizer(TransformComponent):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    deidentifier: TextDeidentifier
    thread_id: str

    def __call__(self, nodes, **kwargs):
        # sync bridge to acall via LlamaIndex's async runner
        ...

    async def acall(self, nodes, **kwargs):
        for node in nodes:
            node.text = await self.deidentifier.anonymize(node.text, self.thread_id)
        return nodes
```

Placed in `transformations` before the embedding model, e.g.
`VectorStoreIndex.from_documents(docs, transformations=[splitter, PIINodeAnonymizer(...), embed_model])`
or an `IngestionPipeline`. Because the transform runs before the embedder, the
embedding provider only ever sees tokens.

`node.text` is read and set via the node's text attribute, consistent with the
`TextCleaner` cookbook example. The sync `__call__` bridges to the async `acall`
so both `IngestionPipeline.run` (sync) and `arun` (async) work.

### 2. `PIIQueryEngine(BaseQueryEngine)`

A wrapper around any query engine that anonymizes the query and restores the
answer.

```python
class PIIQueryEngine(BaseQueryEngine):
    def __init__(self, inner, deidentifier, thread_id, callback_manager=None):
        super().__init__(callback_manager)
        self._inner = inner
        self._deidentifier = deidentifier
        self._thread_id = thread_id

    async def _aquery(self, query_bundle):
        anon = await self._deidentifier.anonymize(query_bundle.query_str, self._thread_id)
        response = await self._inner.aquery(anon)
        response.response = await self._deidentifier.deanonymize(
            response.response, self._thread_id
        )
        return response

    def _query(self, query_bundle):
        # sync bridge to _aquery
        ...

    def _get_prompt_modules(self):
        return {}
```

The wrapper anonymizes `query_bundle.query_str` into the shared thread, so the
retriever searches the anonymized space and matches the anonymized corpus, then
delegates to the inner engine, then deanonymizes `response.response`. It carries
the answer restoration that a `NodePostprocessor` could not, since it runs around
synthesis rather than before it. `response.source_nodes` stay anonymized in v1
(they are the anonymized corpus text); restoring them is out of scope.

### 3. Package and exposure

`src/piighost/integrations/llama_index/` behind the `llama-index` extra. A guarded
module holds both classes:

```python
if importlib.util.find_spec("llama_index") is None:
    raise ImportError(
        "The LlamaIndex integration requires the llama-index package. "
        "Install it with: pip install piighost[llama-index]"
    )
```

`__init__.py` exposes `PIINodeAnonymizer` and `PIIQueryEngine` lazily via
`__getattr__`, so importing the package without the extra fails only on access,
matching the optional-dependency pattern used across the codebase.

## Data flow

Ingestion: documents -> splitter -> `PIINodeAnonymizer` (tokens) -> embedder ->
index. The embedding provider sees only tokens.

Query: question -> `PIIQueryEngine` anonymizes -> retriever searches the
anonymized space -> synthesis over anonymized nodes (the LLM sees only tokens) ->
tokenized answer -> deanonymized for the user.

## Error handling

- Importing the module without the extra raises `ImportError` naming
  `piighost[llama-index]` (module-level guard). The guard message contains
  `piighost[`, so `tests/regression/test_imports.py` auto-skips it when the extra
  is absent.
- `PIIQueryEngine` and `PIINodeAnonymizer` require a `TextDeidentifier`, whose
  construction already enforces a recognizable token grammar
  (`UnrecognizableFactoryError`), so a non-restorable factory is refused up front.
- The sync `__call__` / `_query` bridges use LlamaIndex's own async runner
  (`llama_index.core.async_utils.asyncio_run`) so they behave the way the
  framework's other sync entry points do. The native async paths are `acall` and
  `_aquery`.

## Testing

- `tests/integrations/llama_index/` guarded by `pytest.importorskip("llama_index")`.
  A `llama-index` dependency-group installs `llama-index-core` so the tests run
  under `uv run --group llama-index pytest`; the default `uv run pytest` skips
  them.
- The pipeline under test is `ThreadAnonymizationPipeline(ExactMatchDetector(...))`
  over `InMemoryConversationMemory`, wrapped in a `TextDeidentifier`, so no model
  loads and no network call is made.
- `PIINodeAnonymizer`: build `TextNode`s, run `acall`, assert each `node.text` is
  anonymized and a shared value keeps one token across nodes.
- `PIIQueryEngine`: a fake inner engine exposing `aquery`/`query` returns a
  `Response` whose `.response` holds a token; wrap it, query, assert the query
  reached the inner engine anonymized and the returned `.response` is restored.
- `tests/regression/test_imports.py` auto-covers the optional-extra guard.

## Example

`examples/llama_index/rag.py`, a PEP 723 inline-metadata script mirroring
`examples/langchain/rag.py`: build a `VectorStoreIndex` over a tiny corpus with
`PIINodeAnonymizer` in the transformations, wrap the query engine with
`PIIQueryEngine`, ask a question, and print what OpenAI saw (tokens) versus the
restored answer. It uses OpenAI embeddings and LLM (OPENAI_API_KEY via dotenv)
and an `ExactMatchDetector` for a deterministic demo, matching the LangChain
example's shape.

## Documentation

- `docs/en/examples/llama-index.md` and `docs/fr/examples/llama-index.md`, an
  example page mirroring the LangChain RAG example page, added to the nav in
  `zensical.toml` and `zensical.fr.toml`. Code blocks byte-identical between EN
  and FR.
- Remove the "LlamaIndex integration" / "Intégration LlamaIndex" section from
  `docs/en/roadmap.md` and `docs/fr/roadmap.md` (now shipped).

## Out of scope

- Anonymizing after retrieval (a `NodePostprocessor`): it cannot protect the
  embedding call, which is the stated requirement.
- Restoring `response.source_nodes` text (they stay anonymized in v1).
- A config model: the integration is programmatic, like the middleware.
- Any change to the pipeline, memory, or placeholder stages.
