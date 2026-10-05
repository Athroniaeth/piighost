---
icon: lucide/link
---

# Intégration LlamaIndex

Vous voulez un RAG LlamaIndex où ni le fournisseur d'embeddings ni le LLM ne voient de données confidentielles. `piighost` fournit deux composants. `PIINodeAnonymizer` est une transformation d'ingestion qui dé-identifie chaque node avant l'embedding. `PIIQueryEngine` enveloppe le moteur de requête, dé-identifie la requête et restaure la réponse. Les deux partagent un pipeline de conversation, donc une valeur garde le même jeton à travers le corpus et la requête.

Pour la même idée orchestrée à la main sur un flux RAG simple, voir le script `examples/langchain/rag.py`. Cette page emballe cette idée en objets LlamaIndex réutilisables.

!!! note "Prérequis"
    `piighost` installé avec l'extra llama-index, `pip install "piighost[llama-index]"`, plus `llama-index-embeddings-openai` et `llama-index-llms-openai` et un `OPENAI_API_KEY`.

## 1. Construire le pipeline de conversation

Le pipeline dé-identifie et restaure sur une conversation dédiée au corpus. Ici un `ExactMatchDetector` garde l'exemple déterministe. Remplacez-le par un détecteur à modèle pour du vrai texte.

```python
--8<-- "snippets/llama_index_rag.py:pipeline"
```

## 2. Dé-identifier à l'ingestion, avant l'embedding

Placez `PIINodeAnonymizer` dans les transformations avant le modèle d'embedding, pour que l'index soit bâti sur des jetons et que le fournisseur d'embeddings ne voie jamais de données confidentielles.

```python
--8<-- "snippets/llama_index_rag.py:ingest"
```

## 3. Envelopper le moteur de requête

`PIIQueryEngine` dé-identifie la requête dans la même conversation que le corpus, et restaure la réponse pour l'utilisateur. La recherche porte donc sur le corpus dé-identifié.

```python
--8<-- "snippets/llama_index_rag.py:query"
```

La réponse est restaurée pour l'affichage. Sa formulation dépend du modèle, par exemple :

```text
--8<-- "snippets/llama_index_rag.out"
```

Le LLM a répondu sur `<<PERSON:1>>`{ .placeholder } et `<<LOCATION:1>>`{ .placeholder }. L'utilisateur voit `Patrick`{ .pii } et `Paris`{ .pii } restaurés. La recherche tourne sur le texte dé-identifié. Il y perd un peu de qualité, en échange de quoi les données confidentielles restent hors de l'appel d'embedding.

## Voir aussi

- [Intégration LangChain](langchain.md) : dé-identifier un agent LangChain avec le middleware.
- [Roadmap](../roadmap.md) : ce qui est prévu par ailleurs.
- Le script exécutable est dans `examples/llama_index/rag.py`.
