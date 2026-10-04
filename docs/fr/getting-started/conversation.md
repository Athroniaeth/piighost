---
icon: lucide/messages-square
---

# Pipeline conversationnel

Vous allez construire un `ThreadAnonymizationPipeline` qui garde un jeton stable pour une même valeur d'un message à l'autre. Une valeur vue au message 1 conserve son `<<PERSON:1>>`{ .placeholder } au message 2, au lieu de repartir de zéro à chaque appel. Vous assemblez le pipeline avec une mémoire en RAM, envoyez deux messages de la même conversation, puis effacez la conversation.

!!! note "Prérequis"
    `piighost` installé, voir [Installation](installation.md). Cet exemple n'utilise que le socle, sans extra.

## 1. Assembler le pipeline

`ThreadAnonymizationPipeline` prend les mêmes composants qu'`AnonymizationPipeline` (détecteur, linker, anonymiseur), plus une mémoire de conversation. Seul le détecteur est obligatoire. Le code ci-dessous passe la mémoire explicitement et laisse le linker et l'anonymiseur à leurs valeurs par défaut. La mémoire accumule les détections de chaque message, conversation par conversation. Le pipeline peut ainsi attribuer les jetons sur l'ensemble de la conversation plutôt que sur un message isolé.

`InMemoryConversationMemory` garde cet état dans un dictionnaire du processus. Rien ne survit à un redémarrage et rien n'est partagé entre processus. Cette mémoire convient donc au développement et aux tests. On garde le détecteur simple ici avec `ExactMatchDetector`, qui repère des valeurs connues. Le résultat est ainsi vérifiable, sans modèle.

```python
--8<-- "snippets/conversation.fr.py:setup"
```

## 2. Dé-identifier deux messages de la même conversation

`anonymize` prend le texte et un `thread_id`. Le `thread_id` est obligatoire. Il n'y a pas de conversation partagée par défaut, si bien que deux appelants ne peuvent pas tomber dans la même conversation et se fuiter mutuellement leurs données confidentielles. On envoie deux messages sur la conversation `"thread-42"`.

```python
--8<-- "snippets/conversation.fr.py:turns"


--8<-- "snippets/conversation.fr.py:run"
```

La sortie doit être :

```text
--8<-- "snippets/conversation.fr.out:turns"
```

`Patrick`{ .pii } garde `<<PERSON:1>>`{ .placeholder } du premier au second message, et `Paris`{ .pii } garde `<<LOCATION:1>>`{ .placeholder }. Avec un `AnonymizationPipeline` ordinaire, chaque appel repartirait à `<<PERSON:1>>`{ .placeholder } sans lien avec le message précédent. La mémoire de la conversation est ce qui rend le numéro stable.

## 3. Restaurer une valeur

`deanonymize` reconstruit les jetons de la conversation depuis sa mémoire. Il restaure donc n'importe quel texte qui porte ces jetons, y compris une réponse du modèle que le pipeline n'a jamais dé-identifiée.

```python
--8<-- "snippets/conversation.fr.py:restore"
```

## 4. Oublier une conversation

`forget_thread` efface la mémoire d'une conversation et renvoie le compte de ce qui a été supprimé. Utile pour respecter une demande d'effacement ou libérer la RAM à la fin d'une conversation.

```python
--8<-- "snippets/conversation.fr.py:forget"
```

## Comment ça marche

`ThreadAnonymizationPipeline` encapsule le pipeline de base avec une mémoire par conversation. À chaque message, il met en cache les détections, puis attribue les jetons sur l'union des détections de toute la conversation, pas du seul message courant. Une valeur reçoit donc un jeton pour l'ensemble de la conversation. Le rendu reste par message. Seules les positions du message courant sont remplacées, car chaque message compte ses positions depuis son propre début.

## Et ensuite

- Pour partager la mémoire entre plusieurs processus, remplacez `InMemoryConversationMemory` par une mémoire persistante. Voir la [Référence TOML](../configuration/toml.md) pour la déclarer en configuration.
- Pour brancher ce pipeline dans un agent LangGraph, voir le [Middleware LangChain](langchain.md).
- Pour lire les règles de gestion d'une conversation, de `BR-CONV-01` à `BR-CONV-11`, voir [Suivre une conversation et restaurer la réponse](../../../openwiki/fr/processes/follow-a-conversation.md).
