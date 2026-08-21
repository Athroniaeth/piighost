---
icon: lucide/link
---

# Garder les PII hors d'un pipeline RAG LlamaIndex

Vous voulez un RAG LlamaIndex où ni le fournisseur d'embeddings ni le LLM ne voient de PII. `piighost` fournit deux composants : `PIINodeAnonymizer`, un transform d'ingestion qui anonymise chaque node avant l'embedding, et `PIIQueryEngine`, un wrapper qui anonymise la requête et restaure la réponse. Les deux partagent un pipeline de thread, donc une valeur garde le même token à travers le corpus et la requête.

Pour la même idée orchestrée à la main sur un flux RAG simple, voir le script `examples/langchain/rag.py` ; cette page l'emballe en objets LlamaIndex réutilisables.

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

- [Intégration LangChain](langchain.md) : dé-identifier un agent LangChain avec le middleware.
- [Roadmap](../roadmap.md) : ce qui est prévu par ailleurs.
