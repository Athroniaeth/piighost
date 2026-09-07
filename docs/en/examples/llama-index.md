---
icon: lucide/link
---

# Keep PII out of a LlamaIndex RAG pipeline

You want a LlamaIndex RAG where neither the embedding provider nor the LLM ever sees PII. `piighost` gives you two components: `PIINodeAnonymizer`, an ingestion transform that de-identifies each node before it is embedded, and `PIIQueryEngine`, a wrapper that de-identifies the query and restores the answer. Both share one thread pipeline, so a value keeps the same token across the corpus and the query.

For the same idea orchestrated by hand over a plain RAG flow, see the `examples/langchain/rag.py` script. This page packages it as reusable LlamaIndex objects.

!!! note "Prerequisites"
    `piighost` installed with the llama-index extra, `pip install piighost[llama-index]`, plus `llama-index-embeddings-openai` and `llama-index-llms-openai` and an `OPENAI_API_KEY`.

## 1. Build the thread pipeline

The pipeline de-identifies and restores over a corpus thread. Here an `ExactMatchDetector` keeps the example deterministic. Swap in a model detector for real text.

```python
from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import ThreadAnonymizationPipeline

THREAD = "docs"
detector = ExactMatchDetector({"Patrick": "PERSON", "Paris": "LOCATION"})
pipeline = ThreadAnonymizationPipeline(detector)
```

## 2. De-identify at ingestion, before embedding

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

`PIIQueryEngine` de-identifies the query into the same thread, so retrieval matches the de-identified corpus, and restores the answer for the user.

```python
from llama_index.llms.openai import OpenAI

from piighost.integrations.llama_index import PIIQueryEngine

Settings.llm = OpenAI(model="gpt-5.6-terra")
engine = PIIQueryEngine(
    inner=index.as_query_engine(),
    pipeline=pipeline,
    thread_id=THREAD,
)
answer = engine.query("Where does Patrick live?")
print(answer.response)
```

The LLM answered over `<<PERSON:1>>`{ .placeholder } and `<<LOCATION:1>>`{ .placeholder }. The user sees `Patrick`{ .pii } and `Paris`{ .pii } restored. Retrieval runs on the de-identified space, which trades some quality for keeping PII out of the embedding call.

## See also

- [LangChain integration](langchain.md): de-identify a LangChain agent with the middleware.
- [Roadmap](../roadmap.md): what else is planned.
- The runnable script is in `examples/llama_index/rag.py`.
