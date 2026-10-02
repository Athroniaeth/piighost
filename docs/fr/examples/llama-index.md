---
icon: lucide/link
---

# Garder les données confidentielles hors d'un pipeline RAG LlamaIndex

Vous voulez un RAG LlamaIndex où ni le fournisseur d'embeddings ni le LLM ne voient de données confidentielles. `piighost` fournit deux composants : `PIINodeAnonymizer`, un transform d'ingestion qui dé-identifie chaque node avant l'embedding, et `PIIQueryEngine`, un wrapper qui dé-identifie la requête et restaure la réponse. Les deux partagent un pipeline de thread, donc une valeur garde le même token à travers le corpus et la requête.

Pour la même idée orchestrée à la main sur un flux RAG simple, voir le script `examples/langchain/rag.py`. Cette page l'emballe en objets LlamaIndex réutilisables.

!!! note "Prérequis"
    `piighost` installé avec l'extra llama-index, `pip install piighost[llama-index]`, plus `llama-index-embeddings-openai` et `llama-index-llms-openai` et un `OPENAI_API_KEY`.

## 1. Construire le pipeline de thread

Le pipeline dé-identifie et restaure sur un thread corpus. Ici un `ExactMatchDetector` garde l'exemple déterministe. Remplacez-le par un détecteur à modèle pour du vrai texte.

```python
--8<-- "snippets/llama_index_rag.py:pipeline"
```

## 2. Dé-identifier à l'ingestion, avant l'embedding

Placez `PIINodeAnonymizer` dans les transformations avant le modèle d'embedding, pour que l'index soit bâti sur des tokens et que le fournisseur d'embeddings ne voie jamais de données confidentielles.

```python
--8<-- "snippets/llama_index_rag.py:ingest"
```

## 3. Envelopper le query engine

`PIIQueryEngine` dé-identifie la requête dans le même thread, donc le retrieval concorde avec le corpus dé-identifié, et restaure la réponse pour l'utilisateur.

```python
--8<-- "snippets/llama_index_rag.py:query"
```

Le LLM a répondu sur `<<PERSON:1>>`{ .placeholder } et `<<LOCATION:1>>`{ .placeholder }. L'utilisateur voit `Patrick`{ .pii } et `Paris`{ .pii } restaurés. Le retrieval tourne sur l'espace dé-identifié, ce qui échange un peu de qualité contre le fait de garder les données confidentielles hors de l'appel d'embedding.

## Voir aussi

- [Intégration LangChain](langchain.md) : dé-identifier un agent LangChain avec le middleware.
- [Roadmap](../roadmap.md) : ce qui est prévu par ailleurs.
- Le script exécutable est dans `examples/llama_index/rag.py`.
