---
type: workflow
title: Brancher la protection sur un agent et ses outils
description: Ce que voient le modèle, les outils et l'utilisateur quand PIIGhost protège un agent LangChain, Pydantic AI, LlamaIndex ou Claude Code, quelles options changent ce partage, et où vit chaque règle dans le code.
tags: [integrations, langchain, pydantic-ai, llama-index, claude-code, client, tool-calls, thread-id]
sources:
  - id: openwiki-source-60f405cf9fd8c0cba8a61889
    resource: repo://src/piighost/integrations/_deidentify.py
  - id: openwiki-source-9703fc61b3e278e6ef8403ff
    resource: repo://src/piighost/integrations/claude_code/hooks.py
  - id: openwiki-source-c469f9c4e3d15d32abf9692f
    resource: repo://src/piighost/integrations/claude_code/runner.py
  - id: openwiki-source-a8fd2755cc1e33939a1b3ecb
    resource: repo://src/piighost/integrations/client/remote.py
  - id: openwiki-source-85881a85af445f438a8d7d5f
    resource: repo://src/piighost/integrations/langchain/middleware.py
  - id: openwiki-source-0893e40bf380b075c325a32c
    resource: repo://src/piighost/integrations/llama_index/query_engine.py
  - id: openwiki-source-b43ea3b38b4c09af8aeccb0d
    resource: repo://src/piighost/integrations/llama_index/transform.py
  - id: openwiki-source-d998a4e1822dbcfab4a92c61
    resource: repo://src/piighost/integrations/pydantic_ai/hooks.py
generated: { by: "claude-code", at: "2026-10-02T18:00:00.000Z" }
---

# Brancher la protection sur un agent et ses outils

## En bref

- Branché sur un agent, PIIGhost masque les messages avant le modèle et remet les vraies valeurs dans la réponse.
- Par défaut, les outils de l'agent (recherche, envoi de mail, lecture de fichier) reçoivent les vraies valeurs, et ce qu'ils renvoient est masqué avant le modèle.
- Une conversation sans identifiant est refusée, avec LangChain comme avec Claude Code. Sinon, toutes les conversations partageraient leurs jetons.
- Avec Claude Code, la réponse affichée garde les jetons : aucun point d'accroche ne permet de la réécrire.
- L'historique gardé par l'agent contient les vraies valeurs. Protégez-le comme une donnée personnelle.

Les termes sont définis dans le [glossaire](../glossaire.md). Le mécanisme du fil est décrit dans [Suivre une conversation et restaurer la réponse](../processus/suivre-une-conversation.md).

## Pour le métier

PIIGhost n'a pas d'écran. Les réglages se font dans le code de l'agent ou dans sa configuration. Cette partie décrit ce que chaque acteur voit et les choix à arbitrer.

### Qui voit quoi

| Acteur | LangChain, Pydantic AI | LlamaIndex | Claude Code |
|---|---|---|---|
| Le modèle | des jetons | des jetons (question et documents indexés) | des jetons (demande et résultats d'outils listés) |
| Les outils | les vraies valeurs (réglage par défaut) | sans objet | les vraies valeurs |
| L'utilisateur final | la réponse avec les vraies valeurs | la réponse avec les vraies valeurs | la réponse avec des jetons |
| Le service d'indexation | sans objet | des jetons | sans objet |

### Choisir le traitement des outils

Quatre réglages décident de ce que reçoit l'outil et de ce que lit le modèle. Le choix se fait pour tout l'agent. Le tableau des réglages, l'exemple suivi et les règles sont dans [Laisser un outil agir sur les vraies valeurs](../processus/laisser-un-outil-agir.md).

### Règles à connaître

**BR-AGT-01.** Quand un agent LangChain est appelé sans identifiant de conversation, alors il s'arrête sur `No thread_id in the LangGraph config; pass config={'configurable': {'thread_id': ...}} on the agent call, or 'default' if your conversations need no separation.` Pourquoi : sans identifiant, toutes les conversations tomberaient dans le même fil et partageraient leurs jetons. Une application qui n'a pas besoin de séparer ses conversations passe `default` elle-même.

**BR-AGT-02.** Quand le modèle écrit un jeton que PIIGhost n'a jamais émis, alors la réponse est refusée par défaut, avec `Deanonymized text holds tokens the pipeline never issued`. Deux autres choix existent : garder le jeton tel quel, ou le retirer du texte.

**BR-AGT-03.** Quand l'assistant cite le premier une valeur, alors elle reste en clair par défaut. Exemple : l'assistant répond « Le siège est à Lyon ». « Lyon » vient de lui, il n'est pas masqué au tour suivant. Deux autres choix : la masquer comme une donnée de l'utilisateur, ou ne pas analyser du tout les messages de l'assistant.

**BR-AGT-04.** Quand le réglage d'outil est « Complet » ou « Sortie seule », alors le texte renvoyé par l'outil passe par le repérage complet et est masqué avant le modèle. Avec LangChain, seul le texte du message de l'outil est masqué. Avec Pydantic AI, un résultat structuré (liste, dictionnaire) est parcouru en entier.

**BR-AGT-05.** Quand un événement de Claude Code n'a pas d'identifiant de session, alors il est refusé avec `The hook event carries no session_id, the thread its values belong to.` Aucun fil commun n'est utilisé.

**BR-AGT-06.** Quand un outil de Claude Code n'est pas dans la liste des outils traités, alors son résultat passe en clair. Outils traités : Bash, Read, Write, Edit, Agent, WebFetch, WebSearch, ToolSearch. Grep, notamment, n'y est pas.

**BR-AGT-07.** Quand la réponse du modèle est diffusée au fil de l'eau, alors l'affichage montre des jetons jusqu'à la fin du message, sauf si l'application branche le décodeur de flux prévu. Voir [Afficher une réponse streamée](../processus/afficher-une-reponse-streamee.md).

### Ce que voit l'utilisateur final

- Avec LangChain, Pydantic AI et LlamaIndex : une réponse lisible, avec les vraies valeurs.
- Avec Claude Code : une réponse qui contient des jetons comme `<<PERSON:1>>`. Les fichiers modifiés et les commandes lancées, eux, portent les vraies valeurs.

### Questions fréquentes

**La réponse affichée contient `<<PERSON:1>>`.** Trois causes possibles. Vous utilisez Claude Code, qui ne restaure pas la réponse affichée. Ou l'application diffuse la réponse sans décodeur de flux (BR-AGT-07). Ou la restauration a lieu dans un autre fil que la protection : vérifiez que le même identifiant de conversation est passé aux deux.

**L'agent s'arrête avec `No thread_id in the LangGraph config`.** L'appel ne transmet pas d'identifiant de conversation. Demandez à l'équipe de développement de le passer à chaque appel, ou `default` si les conversations n'ont pas besoin d'être séparées (BR-AGT-01).

**L'agent s'arrête avec `Deanonymized text holds tokens the pipeline never issued`.** Le modèle a écrit un jeton inconnu, souvent en recopiant un jeton d'une autre conversation ou d'un document. Gardez le refus si vous préférez une erreur visible à un texte douteux (BR-AGT-02).

**Un outil a reçu `<<EMAIL:1>>` au lieu de l'adresse.** Le réglage d'outil est « Sortie seule » ou « Aucun ». Passez-le à « Complet » si l'outil doit agir sur la vraie adresse. Voir [Laisser un outil agir](../processus/laisser-un-outil-agir.md).

**Le résultat d'une recherche Grep est parti en clair dans Claude Code.** Grep n'est pas dans la liste des outils traités (BR-AGT-06). Retirez Grep de la session, ou faites ajouter l'outil à la liste.

## Pour les développeurs

### Où vivent les règles

| Règle | Emplacement |
|---|---|
| BR-AGT-01 | `src/piighost/integrations/langchain/middleware.py:47-66` (`_thread_id`) |
| BR-AGT-02 | `src/piighost/integrations/_deidentify.py:133-155`, défaut `RAISE` ligne 57 |
| BR-AGT-03 | `src/piighost/integrations/langchain/middleware.py:370` (`_message_role`), `pipeline/thread.py:322-329` |
| BR-AGT-04 | `middleware.py:220-272` (LangChain), `pydantic_ai/hooks.py:138-154` (Pydantic AI) |
| BR-AGT-05 | `src/piighost/integrations/claude_code/hooks.py:101-105` |
| BR-AGT-06 | `src/piighost/integrations/claude_code/hooks.py:22-38` |
| BR-AGT-07 | `middleware.py:206-218`, `_deidentify.py:83-107` |

Composants liés :

- `TextDeidentifier` (`integrations/_deidentify.py`) : logique commune de masquage, restauration et jetons inventés, partagée par LangChain, Pydantic AI et LlamaIndex. Il refuse à la construction un pipeline sans `recognizer` (`UnrecognizableFactoryError`).
- `PIIAnonymizationMiddleware` : `abefore_model`, `aafter_model`, `awrap_tool_call`.
- `pii_hooks(pipeline, thread_id, ...)` : capacité Pydantic AI, `thread_id` fixe ou fonction du `RunContext`.
- `PIINodeAnonymizer` et `PIIQueryEngine` (LlamaIndex) : masquage des nœuds avant embedding, puis masquage de la question et restauration de la réponse dans le même fil de corpus.
- `handle_hook(event, pipeline)` et `run()` (Claude Code) : `run` lit l'événement sur stdin et appelle `piighost-api` à `PIIGHOST_API_URL` (défaut `http://localhost:8000`).
- `PIIGhostClient` : implémente `AnyThreadPipeline` en HTTP (`/v1/anonymize`, `/v1/deanonymize`, `/v1/detect`, `/v1/labels`, `/v1/threads/{id}/tokens`). Il lève `RemoteError` sur une réponse non 2xx.

### Brancher le middleware LangChain

1. Partez de `examples/langchain_middleware.py`.
2. Construisez un `ThreadAnonymizationPipeline` dont la fabrique est délimitée (par défaut `LabelCounterPlaceholderFactory`).
3. Passez-le à `PIIAnonymizationMiddleware(pipeline)`. Ajoutez `tool_strategy`, `invented_strategy` ou `assistant_strategy` seulement pour changer un défaut.
4. Passez `config={"configurable": {"thread_id": "..."}}` à chaque appel de l'agent.
5. Pour un affichage en flux, enveloppez la boucle `agent.astream(..., stream_mode="messages")` dans `middleware.deanonymize_stream(source, thread_id)`.

#### Vérifier

```bash
uv run pytest tests/integrations/langchain
```

Dans une trace de l'agent, le message reçu par le modèle doit contenir `<<PERSON:1>>` et l'argument reçu par l'outil la vraie valeur.

### Pièges

- **L'état LangGraph garde le contenu des messages en clair.** `aafter_model` restaure le contenu dans l'état, et le checkpointer l'enregistre ainsi. Seuls les `tool_calls` restent en jetons (`middleware.py:199-200`). Il en va de même pour l'historique Pydantic AI après `after_model_request`.
- **LangChain re-masque les arguments des `tool_calls` de l'historique**, par précaution, sauf sous `IGNORE`. Pydantic AI ne le fait pas.
- **Les hooks Claude Code tolèrent une forme de sortie inconnue** : ils la laissent passer. Mettez `PIIGHOST_HOOK_LOG` pour voir les formes réelles. Ce journal contient des valeurs restaurées en clair : gardez-le en local et supprimez-le ensuite.
- **Si `piighost-api` est injoignable, `run()` lève une exception** sans la capturer (`claude_code/runner.py:53-71`). [à vérifier] : Claude Code traite un code de sortie autre que 2 comme une erreur non bloquante, ce qui enverrait la demande en clair. Pour trancher : arrêtez `piighost-api`, soumettez une demande avec un nom, et lisez ce que reçoit le modèle. La correction prévue (sortir en code 2) est suivie sous DPO-9 dans [Points à régler](../reference/points-a-regler.md).
- **`PIIQueryEngine` refuse un moteur en flux** (`NotImplementedError`) et ses chemins synchrones passent par `asyncio.run` : appelez `aquery` depuis du code asynchrone.
- **`PIIGhostClient.anonymize` renvoie un dictionnaire de jetons vide.** La correspondance vit sur le serveur. Restaurez avec `deanonymize`.

### Écarts doc / code

Aucun écart constaté sur cette page. La lacune Grep est documentée dans `docs/en/examples/claude-code.md`.

### Tests

| Test | Couvre |
|---|---|
| `tests/integrations/langchain/test_middleware.py` | Identifiant de fil, contenu en blocs, chaque stratégie d'outil, `Command`, jetons inventés, provenance assistant, refus d'une fabrique non délimitée |
| `tests/integrations/langchain/test_middleware_stream.py` | Restauration en flux |
| `tests/integrations/test_pydantic_ai_hooks.py` | Capacité Pydantic AI |
| `tests/integrations/llama_index/` | Transformation des nœuds, moteur de requête |
| `tests/integrations/test_claude_code_hooks.py` | Les trois événements, liste des champs, outil inconnu laissé passer |
| `tests/integrations/client/test_client.py` | Client HTTP |

Non couvert : le comportement de `run()` quand `piighost-api` est injoignable, et la persistance en clair de l'état LangGraph.

Voir aussi [Configurer un pipeline](../exploitation/configuration-et-hub.md).
