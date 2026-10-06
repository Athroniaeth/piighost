---
icon: lucide/arrow-right-left
description: Remplacez PresidioReversibleAnonymizer, archivé par LangChain, par piighost. Gardez Presidio, pseudonymisez le prompt et restaurez les PII dans la réponse.
seo_title: Migrer depuis PresidioReversibleAnonymizer vers piighost
---

# Migrer depuis PresidioReversibleAnonymizer

Pour migrer depuis `PresidioReversibleAnonymizer`, enveloppez votre `AnalyzerEngine` Presidio dans un `PresidioDetector` et construisez un `ThreadAnonymizationPipeline` dessus. Appelez ensuite les méthodes `anonymize` et `deanonymize` du pipeline avec un `thread_id`. Presidio continue de détecter les valeurs, et `piighost` les remplace puis les restaure.

L'ancienne classe faisait partie de `langchain-experimental`, que LangChain a [abandonné](https://github.com/langchain-ai/langchain-experimental/issues/87) le 22 mai 2026. Son [dépôt](https://github.com/langchain-ai/langchain-experimental) est archivé, elle ne recevra donc plus de correctif.

!!! note "Prérequis"
    `pip install "piighost[presidio,langchain]"`. L'`AnalyzerEngine` par défaut de Presidio charge le modèle spaCy `en_core_web_lg`, comme le faisait l'ancienne classe. L'extra `langchain` ne sert qu'à l'appel au modèle et au middleware.

## Avant, avec PresidioReversibleAnonymizer

L'ancienne classe détecte avec Presidio, remplace chaque valeur par une fausse valeur tirée de Faker, et garde la correspondance dans l'objet.

```python
--8<-- "snippets/migrate_presidio_before.py:before"
```

Le LLM lit un nom inventé et un email inventé à la place de `Patrick Martin`{ .pii } et `patrick@example.com`{ .pii }. `deanonymize()` remet les vraies valeurs, et `save_deanonymizer_mapping()` écrit la correspondance dans un fichier JSON si vous voulez la garder.

## Après, avec piighost

Le même aller-retour avec `piighost` garde le moteur Presidio et remplace l'objet de l'ancienne classe par un pipeline conversationnel.

```python
--8<-- "snippets/migrate_presidio_after.py:after"
```

La sortie doit être :

```text
--8<-- "snippets/migrate_presidio_after.out:after"
```

Le LLM lit `<<PERSON:1>>`{ .placeholder } et `<<EMAIL:1>>`{ .placeholder }. Le dictionnaire `labels` renomme le type `EMAIL_ADDRESS` de Presidio en `EMAIL`. Il joue aussi le rôle de `analyzed_fields`, puisqu'un type qu'il ne liste pas est écarté. La mémoire de conversation garde la correspondance sous `thread-42`, donc le message suivant du fil reprend les mêmes placeholders.

## Dans un agent LangChain

Si l'ancienne classe était placée dans une chaîne LangChain devant un agent, donnez le même pipeline à `PIIAnonymizationMiddleware` au lieu de l'appeler à la main. Le middleware dé-identifie chaque message, restaure la réponse et, par défaut, donne les vraies valeurs aux outils. Voir [Middleware LangChain](../getting-started/langchain.md).

## Ce qui change

- Des placeholders remplacent les fausses valeurs. `<<PERSON:1>>`{ .placeholder } ne peut pas se confondre avec un vrai nom, alors qu'un nom tiré de Faker le peut. Une factory Faker est écartée exprès, voir la [FAQ](../community/faq.md#puis-je-obtenir-de-fausses-valeurs-realistes-plutot-que-des-jetons).
- La correspondance est propre à une conversation. Un ancien objet gardait une seule correspondance pour tous les textes qu'il voyait, alors que le pipeline en garde une par `thread_id` et l'efface avec `forget_thread`.
- La correspondance est stockée dans une mémoire de conversation, en RAM par défaut, ou dans Redis ou en SQL, qui peuvent chiffrer les valeurs. Elle remplace `save_deanonymizer_mapping()` et `load_deanonymizer_mapping()`. Voir [Déploiement](../deployment.md).
- Les méthodes sont asynchrones, il faut donc les attendre avec `await`.
- La détection s'ouvre à d'autres détecteurs. Presidio peut tourner à côté d'un groupe regex du catalogue ou d'un modèle GLiNER2, voir [Détecteurs prêts à l'emploi](detectors.md).
- L'argument `allow_list` de `anonymize()` devient une liste à laisser en clair dans le pipeline, voir [Masquer ou laisser en clair](overrides.md).
- Le middleware LangChain restaure aussi les arguments des appels d'outils et une réponse en flux, ce que l'ancienne classe ne faisait pas.
