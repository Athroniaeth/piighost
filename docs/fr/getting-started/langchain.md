---
icon: lucide/link
---

# Middleware LangChain

Vous allez brancher `PIIAnonymizationMiddleware` dans un agent LangChain pour que le LLM ne voie jamais que des jetons, pendant que vos outils reçoivent les vraies valeurs. L'utilisateur demande `Où habite Patrick ?`, le modèle raisonne sur `<<PERSON:1>>`{ .placeholder } et `<<LOCATION:1>>`{ .placeholder }, et un outil de recherche reçoit quand même le vrai `Patrick`{ .pii } pour faire son travail. Vous construisez le middleware au-dessus d'un `ThreadAnonymizationPipeline`, déclarez un outil, puis exécutez un tour.

!!! note "Prérequis"
    `piighost` installé avec l'extra middleware, `pip install "piighost[langchain]"`, plus un fournisseur LLM configuré pour `create_agent` (ici `openai:...`, donc une `OPENAI_API_KEY`). Le pipeline reprend les composants de la page [Pipeline conversationnel](conversation.md).

## 1. Construire le pipeline de conversation

Le middleware enrobe un `ThreadAnonymizationPipeline`, le même que celui de la page [Pipeline conversationnel](conversation.md). Seul le détecteur est passé. Les autres composants gardent leurs valeurs par défaut, et l'anonymiseur par défaut utilise `LabelCounterPlaceholderFactory`, une fabrique de jetons délimités qui émet `<<PERSON:1>>`{ .placeholder }. Le middleware a besoin de cette forme délimitée pour retrouver un jeton. Avec une autre fabrique, il lève `UnrecognizableFactoryError` à la construction.

```python
--8<-- "snippets/langchain_start.fr.py:pipeline"
```

## 2. Déclarer un outil qui a besoin de la vraie valeur

Un outil qui cherche une personne par son nom a besoin de `Patrick`{ .pii }, pas de `<<PERSON:1>>`{ .placeholder }. Écrivez l'outil comme d'habitude, contre les vraies valeurs. Le middleware les restaure avant l'appel.

```python
--8<-- "snippets/langchain_start.fr.py:tool"
```

## 3. Enrober le pipeline dans le middleware

`PIIAnonymizationMiddleware` prend le pipeline. `tool_strategy=ToolCallStrategy.FULL` restaure les arguments de l'outil à l'entrée et dé-identifie le résultat de l'outil à la sortie. L'outil travaille ainsi sur les vraies valeurs, pendant que le modèle continue de ne voir que des jetons.

```python
--8<-- "snippets/langchain_start.fr.py:agent"
```

## 4. Exécuter un tour

Le `thread_id` va dans la config LangGraph, sous `configurable`. Le middleware l'y lit et rattache chaque jeton à cette conversation.

```python
--8<-- "snippets/langchain_start.fr.py:run"
```

Le message final est restauré pour l'affichage, donc la réponse se lit avec les vraies valeurs. Sa formulation dépend du modèle, par exemple :

```text
--8<-- "snippets/langchain_start.fr.out"
```

## Comment ça marche

Le middleware est un adaptateur mince autour du pipeline. Avant l'appel du modèle, `abefore_model` fait passer chaque message dans `pipeline.anonymize`, si bien que le LLM reçoit `Où habite <<PERSON:1>> ?` au lieu du vrai nom. Quand le modèle appelle `lookup_city` avec `person="<<PERSON:1>>"`, `awrap_tool_call` sous `ToolCallStrategy.FULL` restaure l'argument en `Patrick`{ .pii } avant d'exécuter l'outil. Il dé-identifie ensuite à nouveau le résultat texte de l'outil. Après l'appel du modèle, `aafter_model` restaure la réponse pour l'utilisateur. Le `thread_id` garde `<<PERSON:1>>`{ .placeholder } lié à `Patrick`{ .pii } à chaque étape du tour.

Deux règles méritent d'être connues. Un appel sans identifiant de conversation échoue. Le middleware ne range pas toutes les conversations dans une seule conversation partagée, où les jetons fuiteraient de l'une à l'autre. Si vos conversations n'ont pas besoin d'être séparées, passez `"default"`. `invented_strategy=InventedPlaceholderStrategy.RAISE` refuse un jeton qui apparaît dans la réponse du modèle mais que le pipeline n'a jamais émis, qu'il soit halluciné ou injecté.

## Voir aussi

- Pour choisir un autre comportement d'outil, `INPUT` seul, `OUTPUT` seul ou `PASSTHROUGH`, voir [Stratégies d'appel d'outil](../tool-call-strategies.md).
- Pour un agent complet avec un vrai détecteur et un system prompt, voir [Intégration LangChain](../examples/langchain.md).
- Pour exécuter le pipeline hors du processus contre un serveur partagé, voir [Client distant](api-client.md).
