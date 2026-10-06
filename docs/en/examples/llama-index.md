---
icon: lucide/link
seo_title: LlamaIndex RAG that masks PII
description: De-identify LlamaIndex nodes before embedding and wrap the query engine, so neither the embedding provider nor the LLM sees PII. Answers are restored.
---

# LlamaIndex integration

You want a LlamaIndex RAG where neither the embedding provider nor the LLM ever sees confidential data. `piighost` gives you two components. `PIINodeAnonymizer` is an ingestion transform that de-identifies each node before it is embedded. `PIIQueryEngine` is a wrapper that de-identifies the query and restores the answer. Both share one thread pipeline, so a value keeps the same token across the corpus and the query.

For the same idea orchestrated by hand over a plain RAG flow, see the `examples/langchain/rag.py` script. This page packages that idea as reusable LlamaIndex objects.

!!! note "Prerequisites"
    `piighost` installed with the llama-index extra, `pip install "piighost[llama-index]"`, plus `llama-index-embeddings-openai` and `llama-index-llms-openai` and an `OPENAI_API_KEY`.

## 1. Build the thread pipeline

The pipeline de-identifies and restores over a corpus thread. Here an `ExactMatchDetector` keeps the example deterministic. Swap in a model detector for real text.

```python
--8<-- "snippets/llama_index_rag.py:pipeline"
```

## 2. De-identify at ingestion, before embedding

Put `PIINodeAnonymizer` in the transformations before the embedding model, so the index is built on tokens and the embedding provider never sees confidential data.

```python
--8<-- "snippets/llama_index_rag.py:ingest"
```

## 3. Wrap the query engine

`PIIQueryEngine` de-identifies the query into the same thread as the corpus, and restores the answer for the user. Retrieval therefore matches the de-identified corpus.

```python
--8<-- "snippets/llama_index_rag.py:query"
```

The answer is restored for display. Its wording depends on the model, for example:

```text
--8<-- "snippets/llama_index_rag.out"
```

The LLM answered over `<<PERSON:1>>`{ .placeholder } and `<<LOCATION:1>>`{ .placeholder }. The user sees `Patrick`{ .pii } and `Paris`{ .pii } restored. Retrieval runs on the de-identified space. It loses some quality there, and in exchange confidential data stays out of the embedding call.

## See also

- [LangChain integration](langchain.md): de-identify a LangChain agent with the middleware.
- [Roadmap](../roadmap.md): what else is planned.
- The runnable script is in `examples/llama_index/rag.py`.
