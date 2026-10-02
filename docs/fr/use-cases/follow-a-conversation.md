---
icon: lucide/messages-square
---

# Suivre une conversation et restaurer la réponse

Dans une conversation à plusieurs messages, une valeur garde le même placeholder du premier au dernier message, ce qui permet au LLM de suivre le fil. La réponse du LLM est restaurée avant d'être affichée, une personne peut corriger les détections d'un message, et la conversation peut être effacée à la demande.

Répond à : DEV-2, DEV-3, DEV-8, USER-1, USER-2, DPO-6

## Acteurs

- L'utilisateur final, qui écrit en clair et lit la réponse
- L'application, qui nomme la conversation à chaque appel
- `piighost`, qui garde en mémoire les détections de chaque conversation
- Le LLM, qui ne reçoit et n'écrit que des placeholders
- Un relecteur, qui corrige les détections d'un message (facultatif)
- Le DPO, qui demande l'effacement d'une conversation (facultatif)

## Préconditions

- L'application passe par le pipeline conversationnel, directement ou à travers le middleware LangChain ou la capacité Pydantic AI.
- Chaque appel porte l'identifiant de la conversation, ici `conv-1`.
- Les placeholders désignent chacun une seule valeur, comme `<<PERSON:1>>`{ .placeholder }, ce qui est le réglage par défaut.

## Scénario nominal

1. L'utilisateur écrit un premier message, que le LLM reçoit dé-identifié:

    ```text
    Je suis Jean Dupont, jean.dupont@exemple.fr
    Je suis <<PERSON:1>>, <<EMAIL:1>>
    ```

2. L'utilisateur écrit un second message. L'adresse déjà vue reprend `<<EMAIL:1>>`{ .placeholder }, la nouvelle personne prend le numéro suivant:

    ```text
    Mettez Marie Curie en copie de jean.dupont@exemple.fr
    Mettez <<PERSON:2>> en copie de <<EMAIL:1>>
    ```

3. Le LLM répond avec les placeholders qu'il a reçus:

    ```text
    Bonjour <<PERSON:1>>, j'écris à <<EMAIL:1>> avec <<PERSON:2>> en copie.
    ```

4. `piighost` remplace chaque placeholder de la conversation par sa valeur:

    ```text
    Bonjour Jean Dupont, j'écris à jean.dupont@exemple.fr avec Marie Curie en copie.
    ```

5. L'application affiche cette réponse restaurée.
6. Trois messages plus tard, "Rappelez Jean Dupont demain" part encore sous la forme "Rappelez `<<PERSON:1>>`{ .placeholder } demain".

## Scénarios alternatifs

### A1. L'identifiant de conversation manque

Avec le middleware LangChain, un appel sans identifiant de conversation est refusé par défaut, avec une erreur `MissingThreadIdError` qui indique comment le passer. Rien n'est envoyé au LLM. Si l'application a choisi de tolérer cet oubli, l'appel retombe sur une conversation partagée nommée `default`, avec un avertissement dans les journaux, et tous les utilisateurs sans identifiant partagent alors leurs placeholders.

### A2. Le LLM écrit un placeholder qui n'a jamais été émis

Le LLM répond "Bonjour `<<PERSON:1>>`{ .placeholder } et `<<PERSON:9>>`{ .placeholder }." alors que `<<PERSON:9>>`{ .placeholder } n'existe pas dans la conversation. Il l'a inventé, ou un texte injecté l'y a placé. Le réglage choisi décide de ce que voit l'utilisateur.

| Réglage | Résultat |
|---|---|
| Refuser (par défaut) | erreur `Deanonymized text holds tokens the pipeline never issued: ['<<PERSON:9>>']`, rien n'est affiché |
| Retirer | "Bonjour Jean Dupont et ." |
| Garder | "Bonjour Jean Dupont et `<<PERSON:9>>`{ .placeholder }." |

Un texte sans numéro, comme `<<PERSON>>`, n'a pas la forme des placeholders émis et passe tel quel.

### A3. L'assistant cite le premier une valeur

Le LLM écrit "Le rendez-vous est à Lyon.", puis l'utilisateur écrit "Jean Dupont ira à Lyon.". Le LLM reçoit "`<<PERSON:1>>`{ .placeholder } ira à Lyon.". `Lyon`{ .pii } reste en clair dans toute la conversation, car le LLM l'a apporté lui-même. Un réglage permet de dé-identifier aussi ces valeurs.

### A4. Une autre conversation cite les mêmes personnes

Dans la conversation `conv-2`, "Marie Curie et Jean Dupont" part sous la forme "`<<PERSON:1>>`{ .placeholder } et `<<PERSON:2>>`{ .placeholder }". Les numéros sont propres à chaque conversation. Restaurer "Bonjour `<<PERSON:1>>`{ .placeholder }" donne `Jean Dupont`{ .pii } dans `conv-1` et `Marie Curie`{ .pii } dans `conv-2`.

### A5. Un relecteur corrige les détections d'un message

La conversation contient deux messages:

```text
Je suis Jean Dupont, jean.dupont@exemple.fr       → Je suis <<PERSON:1>>, <<EMAIL:1>>
Mon associée Marie Curie et Jean Dupont           → Mon associée <<PERSON:2>> et <<PERSON:1>>
```

Le relecteur retire `Jean Dupont`{ .pii } des détections du premier message. Ce message part désormais sous la forme "Je suis Jean Dupont, `<<EMAIL:1>>`{ .placeholder }". La correction ne touche que ce message, `Jean Dupont`{ .pii } reste dé-identifié dans le second. Les numéros sont recalculés sur toute la conversation, et le second message devient "Mon associée `<<PERSON:1>>`{ .placeholder } et `<<PERSON:2>>`{ .placeholder }".

!!! warning "Une correction peut renuméroter la conversation"
    Après la correction, `<<PERSON:1>>`{ .placeholder } désigne `Marie Curie`{ .pii }. Une réponse du LLM écrite avant la correction, "Bonjour `<<PERSON:1>>`{ .placeholder }", est restaurée en "Bonjour Marie Curie" alors qu'elle parlait de `Jean Dupont`{ .pii }. Relancez la conversation à partir du message corrigé.

### A6. Le DPO demande l'effacement de la conversation

L'application efface `conv-1`. `piighost` supprime sa mémoire et rend le compte de ce qui a été supprimé, ici `Forgotten(messages=5, detections=8)` pour les cinq messages de la conversation. Ensuite, "Bonjour `<<PERSON:1>>`{ .placeholder }" n'est plus restauré et reste tel quel. La conversation `conv-2` n'est pas touchée.

## Règles

| Règle | Énoncé |
|---|---|
| BR-CONV-01 | Chaque appel du pipeline conversationnel nomme sa conversation, et il n'existe pas de conversation par défaut à ce niveau. |
| BR-CONV-02 | Une valeur garde son placeholder dans toute la conversation, et une nouvelle valeur du même type prend le numéro suivant. |
| BR-CONV-03 | Deux conversations ne partagent rien, chacune numérote ses valeurs de son côté. |
| BR-CONV-04 | La restauration remplace tout placeholder émis dans la conversation, y compris dans un texte que `piighost` n'a jamais dé-identifié, comme la réponse du LLM. |
| BR-CONV-05 | Avec le middleware LangChain ou la capacité Pydantic AI, un placeholder jamais émis est refusé par défaut, et peut être retiré ou gardé sur réglage. |
| BR-CONV-06 | Le pipeline conversationnel utilisé seul laisse un placeholder inconnu tel quel. |
| BR-CONV-07 | Une valeur citée d'abord par l'assistant reste en clair dans toute la conversation, sauf réglage contraire. |
| BR-CONV-08 | Une correction remplace les détections d'un seul message, et les listes du serveur s'appliquent encore à la correction. |
| BR-CONV-09 | Une correction qui ajoute ou retire une valeur dans un message ancien peut changer les numéros de toute la conversation. |
| BR-CONV-10 | Un message identique renvoyé dans la même conversation reprend ses détections enregistrées, sans relancer le détecteur. |
| BR-CONV-11 | L'effacement supprime toute la mémoire de la conversation et rend le nombre de messages et de détections supprimés. |
| BR-CONV-12 | Le middleware LangChain refuse par défaut un appel sans identifiant de conversation. |

## Postconditions

- La mémoire de `conv-1` contient les détections de chaque message, et la correspondance de chaque placeholder se déduit de cette mémoire.
- L'historique envoyé au LLM ne contient que des placeholders.
- Après un effacement, la mémoire de la conversation est vide et ses placeholders ne sont plus restaurés.
- L'utilisateur lit "Bonjour Jean Dupont" et ne voit jamais `<<PERSON:1>>`{ .placeholder }.

## Pour le développeur

Le pipeline conversationnel est `ThreadAnonymizationPipeline`. Chaque méthode prend le `thread_id` explicitement.

- `anonymize(text, thread_id, role=MessageRole.USER)` dé-identifie un message. `role=MessageRole.ASSISTANT` date les valeurs apportées par le LLM.
- `deanonymize(text, thread_id)` restaure un texte. Le pipeline seul n'applique aucune politique aux placeholders inventés.
- `anonymize_corrected(text, thread_id, detections)` enregistre un jeu de détections corrigé, sans départage des recouvrements ni expansion, puis passe par l'`override` configuré.
- `thread_token_map(thread_id)` rend la correspondance placeholder vers valeur, utile pour vérifier une correction.
- `forget_thread(thread_id)` efface la conversation et rend un `Forgotten`. La copie des correspondances gardée en mémoire vive est purgée dans le processus qui l'appelle. Les autres processus gardent la leur jusqu'à son éviction, d'où le paramètre `token_memo_ttl`.

Le middleware LangChain lit `thread_id` dans `config["configurable"]`, lève `MissingThreadIdError` quand `require_thread_id=True` (défaut), et retombe sur `DEFAULT_THREAD_ID` avec un avertissement sinon. `invented_strategy` (`RAISE`, `DROP`, `KEEP`) règle les placeholders inventés et lève `InventedPlaceholderError`. `assistant_strategy` (`PRESERVE`, `ANONYMIZE`, `IGNORE`) règle les valeurs apportées par l'assistant.

À lire ensuite.

- [Pipeline conversationnel](../getting-started/conversation.md)
- [Référence Pipeline](../reference/pipeline.md)
- [Référence de l'intégration LangChain](../reference/langchain.md)
- [Stratégies d'appel outil](../tool-call-strategies.md), pour `InventedPlaceholderStrategy` et `EntityCreateByAssistantStrategy`
- [Référence de la mémoire de conversation](../reference/memory.md)
- [Comment documenter `piighost` dans une AIPD](../dpia.md) et la route d'effacement de la [référence des endpoints de l'API](../reference/api-endpoints.md)
