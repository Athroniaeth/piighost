---
icon: lucide/hammer
---

# Laisser un outil agir sur les vraies valeurs

Un agent appelle des outils, par exemple pour envoyer un e-mail. Le LLM ne connaît que les placeholders et écrit donc `<<EMAIL:1>>`{ .placeholder } dans l'appel. `piighost` restaure les arguments juste avant l'exécution, pour que l'outil agisse sur `jean.dupont@exemple.fr`{ .pii }, puis dé-identifie le résultat de l'outil avant que le LLM le lise.

Répond à : DEV-4, DEV-8, USER-3, DPO-1

## Acteurs

- L'utilisateur final, qui demande une action
- L'application, un agent LangChain ou Pydantic AI
- `piighost`, placé entre le LLM et les outils
- Le LLM, qui décide d'appeler l'outil et écrit ses arguments
- L'outil, ici `send_email`, qui agit sur les vraies valeurs

## Préconditions

- L'agent passe par le middleware LangChain ou la capacité Pydantic AI, qui pilotent le pipeline conversationnel.
- Chaque placeholder désigne une seule valeur, comme `<<EMAIL:1>>`{ .placeholder }, sans quoi `piighost` ne saurait pas quelle valeur remettre dans l'argument.
- La conversation `conv-1` contient déjà le message "Écrivez à `<<PERSON:1>>`{ .placeholder }, `<<EMAIL:1>>`{ .placeholder }", issu de "Écrivez à Jean Dupont, jean.dupont@exemple.fr".
- La stratégie d'appel d'outil est celle par défaut, la restauration des arguments et la dé-identification du résultat.

## Scénario nominal

1. Le LLM décide d'appeler `send_email` avec ces arguments:

    ```json
    {"to": "<<EMAIL:1>>", "body": "Bonjour <<PERSON:1>>"}
    ```

2. `piighost` restaure chaque chaîne des arguments, et l'outil reçoit:

    ```json
    {"to": "jean.dupont@exemple.fr", "body": "Bonjour Jean Dupont"}
    ```

3. L'outil envoie l'e-mail à la bonne adresse et renvoie ce résultat:

    ```text
    Envoyé à jean.dupont@exemple.fr, copie à marie.curie@exemple.fr
    ```

4. `piighost` dé-identifie le résultat dans la conversation. L'adresse connue reprend son placeholder, l'adresse nouvelle prend le numéro suivant, et le LLM lit:

    ```text
    Envoyé à <<EMAIL:1>>, copie à <<EMAIL:2>>
    ```

5. Avec le middleware LangChain, l'historique de la conversation garde l'appel tel que le LLM l'a écrit, avec `<<EMAIL:1>>`{ .placeholder }. Les vraies valeurs n'ont existé que pendant l'exécution de l'outil.
6. Le LLM rédige sa réponse finale, restaurée pour l'utilisateur comme dans [Suivre une conversation et restaurer la réponse](follow-a-conversation.md).

## Scénarios alternatifs

### A1. Une autre stratégie est choisie

La stratégie se choisit par agent, selon ce que les outils lisent et renvoient. Sur le même appel, les quatre stratégies donnent ceci.

| Stratégie | L'outil reçoit `to` | Le LLM lit |
|---|---|---|
| Complète (par défaut) | `jean.dupont@exemple.fr`{ .pii } | "Envoyé à `<<EMAIL:1>>`{ .placeholder }, copie à `<<EMAIL:2>>`{ .placeholder }" |
| Entrée seule | `jean.dupont@exemple.fr`{ .pii } | "Envoyé à jean.dupont@exemple.fr, copie à marie.curie@exemple.fr" |
| Sortie seule | `<<EMAIL:1>>`{ .placeholder } | "Envoyé à `<<EMAIL:1>>`{ .placeholder }, copie à `<<EMAIL:2>>`{ .placeholder }" |
| Aucune | `<<EMAIL:1>>`{ .placeholder } | "Envoyé à jean.dupont@exemple.fr, copie à marie.curie@exemple.fr" |

Avec "Entrée seule" ou "Aucune", le résultat de l'outil arrive au LLM en clair. Ces deux stratégies sont réservées aux outils dont le résultat ne contient aucune donnée confidentielle. Avec "Sortie seule" ou "Aucune", l'outil reçoit le placeholder et enverrait l'e-mail à une adresse qui n'existe pas.

### A2. Le LLM écrit un placeholder qui n'a jamais été émis

Le LLM appelle `send_email` avec `{"to": "<<EMAIL:7>>"}`. Par défaut, `piighost` refuse avec l'erreur `Deanonymized text holds tokens the pipeline never issued: ['<<EMAIL:7>>']`, avant que l'outil s'exécute, donc aucun e-mail ne part. Avec le réglage "retirer", l'outil reçoit `{"to": ""}`. Avec le réglage "garder", il reçoit `{"to": "<<EMAIL:7>>"}`.

### A3. Le LLM écrit une valeur en clair dans un argument

Le LLM écrit `{"to": "jean.dupont@exemple.fr", "cc": "marie.curie@exemple.fr"}` alors que seule la première adresse vient de l'utilisateur. Avec le middleware LangChain, avant l'appel suivant au LLM, l'historique est réécrit en `{"to": "<<EMAIL:1>>", "cc": "marie.curie@exemple.fr"}`. L'adresse connue reprend son placeholder. L'adresse que le LLM a apportée lui-même reste en clair, comme toute valeur citée d'abord par l'assistant.

### A4. La réponse passe par le proxy OpenAI en streaming

Derrière le proxy OpenAI du serveur `piighost-api`, une réponse streamée ne restaure que le texte. Les arguments d'appel d'outil streamés gardent leurs placeholders, alors qu'une réponse non streamée les restaure. Voir [Dé-identifier un client OpenAI avec le proxy](../examples/openai-proxy.md).

## Règles

| Règle | Énoncé |
|---|---|
| BR-TOOL-01 | La stratégie par défaut restaure les arguments avant l'outil et dé-identifie son résultat avant le LLM. |
| BR-TOOL-02 | La stratégie "Entrée seule" restaure les arguments et transmet le résultat au LLM tel que l'outil l'a renvoyé. |
| BR-TOOL-03 | La stratégie "Sortie seule" laisse les placeholders dans les arguments et dé-identifie le résultat. |
| BR-TOOL-04 | La stratégie "Aucune" ne touche ni aux arguments ni au résultat. |
| BR-TOOL-05 | Avec le middleware LangChain, les arguments restaurés ne servent qu'à l'exécution, et l'appel enregistré dans l'historique garde ses placeholders. |
| BR-TOOL-06 | Le résultat d'un outil passe par la détection de la conversation, donc une valeur connue reprend son placeholder et une valeur nouvelle prend le numéro suivant. |
| BR-TOOL-07 | Une valeur apparue d'abord dans le résultat d'un outil compte comme une valeur de l'utilisateur et reste dé-identifiée dans la suite. |
| BR-TOOL-08 | Un placeholder jamais émis dans un argument suit le même réglage que dans une réponse, et le refus par défaut empêche l'outil de s'exécuter. |
| BR-TOOL-09 | La restauration parcourt toutes les chaînes des dictionnaires, listes et tuples imbriqués, et laisse les autres valeurs intactes. |
| BR-TOOL-10 | Avec le middleware LangChain, les arguments des appels d'outil de l'historique sont dé-identifiés à nouveau avant chaque appel au LLM, sauf si les messages de l'assistant ne sont pas analysés. |
| BR-TOOL-11 | Avec le middleware LangChain, seul le texte d'un résultat d'outil est dé-identifié, et les blocs non textuels passent tels quels. |

## Postconditions

- L'outil a agi sur `jean.dupont@exemple.fr`{ .pii }, et l'e-mail est parti à la bonne adresse.
- Le LLM a lu "Envoyé à `<<EMAIL:1>>`{ .placeholder }, copie à `<<EMAIL:2>>`{ .placeholder }".
- La mémoire de la conversation connaît `marie.curie@exemple.fr`{ .pii } sous `<<EMAIL:2>>`{ .placeholder }.
- L'appel d'outil enregistré dans l'historique porte `<<EMAIL:1>>`{ .placeholder }, et l'action de l'utilisateur a porté sur ses vraies données.

## Pour le développeur

Côté LangChain, `PIIAnonymizationMiddleware` agit dans `awrap_tool_call`. Côté Pydantic AI, `pii_hooks` accepte les mêmes stratégies, avec deux écarts. Il dé-identifie aussi un résultat structuré (dictionnaire, liste), et il ne réécrit pas les arguments des appels d'outil de l'historique.

| Stratégie de la page | `ToolCallStrategy` |
|---|---|
| Complète | `FULL` (défaut) |
| Entrée seule | `INPUT` |
| Sortie seule | `OUTPUT` |
| Aucune | `PASSTHROUGH` |

```python
from piighost.integrations.langchain import (
    InventedPlaceholderStrategy,
    PIIAnonymizationMiddleware,
    ToolCallStrategy,
)

middleware = PIIAnonymizationMiddleware(
    pipeline,
    tool_strategy=ToolCallStrategy.FULL,
    invented_strategy=InventedPlaceholderStrategy.RAISE,
)
```

- La restauration des arguments construit un nouvel appel par `request.override(tool_call=...)` et ne modifie jamais le `tool_call` de l'état LangGraph.
- Le résultat est dé-identifié dans le `ToolMessage` renvoyé, ou dans les `ToolMessage` portés par un `Command`.
- Le refus d'un placeholder inventé lève `InventedPlaceholderError` depuis `awrap_tool_call`.
- `assistant_strategy=EntityCreateByAssistantStrategy.IGNORE` désactive la nouvelle dé-identification des arguments de l'historique (BR-TOOL-10).
- Le middleware exige un pipeline dont la factory expose un `recognizer`, sinon il lève `UnrecognizableFactoryError` à la construction.

À lire ensuite.

- [Stratégies d'appel outil](../tool-call-strategies.md)
- [Référence de l'intégration LangChain](../reference/langchain.md)
- [Faire tourner un agent Pydantic AI derrière PIIGhost](../examples/pydantic-ai.md)
- [Placeholder factories](../placeholder-factories.md)
