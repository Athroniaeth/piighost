---
type: workflow
title: Suivre une conversation et restaurer la réponse
description: Comment PIIGhost garde le même jeton pour une valeur sur toute une conversation, restaure la réponse du modèle, traite les valeurs apportées par l'assistant et les jetons inventés, applique une correction humaine et efface une conversation.
tags: [thread, conversation-memory, deanonymize, provenance, invented-placeholder, hitl, erasure, streaming]
sources:
  - id: openwiki-source-a4810bc908328d4c6013f381
    resource: repo://src/piighost/components/placeholder/base.py
  - id: openwiki-source-219ef8159700bea2d8181beb
    resource: repo://src/piighost/components/placeholder/streaming.py
  - id: openwiki-source-beb42dcd927067e197327036
    resource: repo://src/piighost/conversation_memory/base.py
  - id: openwiki-source-19f6f6edbb7533ba166dd534
    resource: repo://src/piighost/conversation_memory/memory.py
  - id: openwiki-source-32946ba53121de4a935726de
    resource: repo://src/piighost/conversation_memory/redis_backend.py
  - id: openwiki-source-60f405cf9fd8c0cba8a61889
    resource: repo://src/piighost/integrations/_deidentify.py
  - id: openwiki-source-07566b3f03a831d37fa4fbce
    resource: repo://src/piighost/pipeline/thread.py
generated: { by: "claude-code", at: "2026-10-02T18:00:00.000Z" }
---
# Suivre une conversation et restaurer la réponse

## En bref

- Dans une conversation, une même valeur garde le même jeton du premier au dernier message.
- Deux conversations sont isolées : le même nom peut y porter le même numéro sans rien partager.
- Chaque appel nomme sa conversation. Un appel sans identifiant est refusé, il ne tombe jamais dans une conversation partagée.
- Une valeur citée d'abord par l'assistant reste en clair, même si l'utilisateur la reprend ensuite.
- Effacer une conversation supprime sa mémoire. Les jetons de cette conversation ne sont plus restaurés ensuite.

Besoins couverts : DEV-2, DEV-3, DEV-8, DEV-10, DEV-11, OPS-2, OPS-7, USER-1, USER-2, USER-6 et DPO-6, décrits dans [Besoins par profil](../besoins-par-profil.md). Les termes sont définis dans le [glossaire](../glossaire.md). Le traitement d'un message isolé est décrit dans [Protéger un message avant l'envoi au modèle](proteger-un-message.md).

## Pour le métier

PIIGhost n'a pas d'écran. Une conversation est désignée par un identifiant que l'application transmet à chaque message. Ce que vous pouvez constater, c'est le texte reçu par le modèle et la réponse affichée.

### Qui intervient

| Acteur | Rôle |
|---|---|
| L'utilisateur final | écrit en clair, lit la réponse restaurée, peut corriger un repérage |
| L'application | nomme la conversation à chaque appel |
| PIIGhost | garde en mémoire les valeurs de chaque conversation |
| Le modèle | ne reçoit et n'écrit que des jetons |
| Le DPO | demande l'effacement d'une conversation |

### Exemple de conversation

| Tour | Auteur | Texte écrit | Texte vu par le modèle |
|---|---|---|---|
| 1 | utilisateur | Je suis Claire Dubois. | Je suis `<<PERSON:1>>`. |
| 2 | utilisateur | Mon collègue Marc Petit et Claire Dubois. | Mon collègue `<<PERSON:2>>` et `<<PERSON:1>>`. |
| 3 | assistant | Le siège est à Lyon. | Le siège est à Lyon. |
| 4 | utilisateur | Je vais à Lyon voir Marc Petit. | Je vais à Lyon voir `<<PERSON:2>>`. |

Si le modèle répond « Bonjour `<<PERSON:1>>`, saluez `<<PERSON:2>>`. », l'utilisateur lit « Bonjour Claire Dubois, saluez Marc Petit. »

**Comment vérifier** : demandez à l'équipe technique la correspondance des jetons de la conversation. Chaque jeton doit désigner une seule personne.

### Corriger un repérage

L'utilisateur, ou l'application en son nom, peut corriger les valeurs d'un message avant l'envoi : ajouter un nom oublié, ou rendre lisible un terme masqué à tort.

1. Repérez le message à corriger.
2. Ajoutez la valeur oubliée avec son type, ou retirez la valeur masquée à tort.
3. Renvoyez le message corrigé.

> [!WARNING]
> Corriger un message ancien peut changer les numéros de toute la conversation (BR-CONV-07). Une réponse déjà écrite par le modèle peut alors être restaurée avec le nom d'une autre personne. Corrigez de préférence le dernier message.

**Comment vérifier** : la valeur ajoutée part sous forme de jeton, la valeur retirée part en clair, et les autres messages ne changent pas.

### Effacer une conversation

Cas typique : une personne exerce son droit à l'effacement.

1. Identifiez la conversation par son identifiant.
2. Demandez son effacement à l'équipe technique, ou appelez la route d'effacement du serveur.
3. Notez le compte rendu : nombre de messages et de valeurs supprimés.

**Comment vérifier** : restaurez un ancien jeton de cette conversation. Il doit rester tel quel, par exemple « Bonjour `<<PERSON:1>>` ».

### Règles à connaître

**BR-CONV-01.** Quand une valeur réapparaît dans un message suivant de la même conversation, alors elle reprend son jeton. Une nouvelle valeur du même type reçoit le numéro suivant.

**BR-CONV-02.** Quand la même valeur apparaît dans deux conversations différentes, alors chacune a sa propre numérotation, et un jeton ne se restaure que dans sa conversation. Exemple : « Marc Petit » est `<<PERSON:2>>` dans une conversation et `<<PERSON:1>>` dans une autre. Restaurer `<<PERSON:1>>` dans une troisième conversation vide le laisse tel quel.

**BR-CONV-03.** Quand un appel ne nomme aucune conversation, alors il est refusé, avant tout envoi au modèle. Une application dont les conversations n'ont pas besoin d'être séparées nomme elle-même la conversation `default`. Pourquoi : sans identifiant, tous les utilisateurs partageraient leurs jetons.

**BR-CONV-04.** Quand l'assistant cite le premier une valeur, alors elle reste en clair pour toute la conversation, même reprise par l'utilisateur (tour 4, « Lyon »). Pourquoi : le modèle connaît déjà cette valeur, et la masquer lui retirerait une connaissance utile. Deux autres réglages existent : la masquer comme une valeur de l'utilisateur, ou ne pas analyser les messages de l'assistant. Une valeur apportée d'abord par l'utilisateur reste masquée, même si l'assistant la répète.

**BR-CONV-05.** Quand la réponse du modèle contient un jeton de la conversation, alors il est remplacé par la vraie valeur, même dans un texte que PIIGhost n'a jamais protégé.

**BR-CONV-06.** Quand la réponse contient un jeton au bon format que PIIGhost n'a jamais émis, alors la restauration est refusée par défaut : `Deanonymized text holds tokens the pipeline never issued: ['<<PERSON:9>>']`. Ce jeton a été inventé par le modèle ou injecté par un texte. Deux autres choix existent : le garder ou le retirer.

| Réglage | « Bonjour `<<PERSON:1>>` et `<<PERSON:9>>`. » devient |
|---|---|
| Refuser (par défaut) | erreur, rien n'est affiché |
| Retirer | « Bonjour Claire Dubois et . » |
| Garder | « Bonjour Claire Dubois et `<<PERSON:9>>`. » |

Un jeton dont la casse ou le numéro a changé (`<<Person:1>>`, `<<PERSON:01>>`) compte comme inventé. Un jeton aux délimiteurs abîmés (`<< PERSON:1 >>`) n'est pas reconnu du tout et reste tel quel.

**BR-CONV-07.** Quand une personne corrige à la main les valeurs d'un message, alors sa correction remplace le repérage automatique de ce message seulement, et la liste blanche et la liste noire s'appliquent encore. Exemple : retirer « Claire Dubois » du tour 1 le laisse en clair au tour 1, et il reste masqué au tour 2. Les numéros peuvent alors changer pour toute la conversation : après ce retrait, `<<PERSON:1>>` désigne Marc Petit et `<<PERSON:2>>` Claire Dubois.

**BR-CONV-08.** Quand un message identique est renvoyé dans la même conversation, alors son repérage n'est pas refait. Le résultat enregistré la première fois est réutilisé.

**BR-CONV-09.** Quand une conversation est effacée, alors toute sa mémoire est supprimée, et l'effacement rend le nombre de messages et de valeurs supprimés. Exemple : `Forgotten(messages=4, detections=5)` pour la conversation ci-dessus. Ensuite, `<<PERSON:1>>` n'est plus restauré et reste tel quel.

**BR-CONV-10.** Quand plusieurs instances du service partagent la même mémoire Redis, alors elles donnent le même jeton à la même valeur d'une conversation, et chacune restaure les jetons émis par l'autre.

**BR-CONV-11.** Quand la mémoire est gardée dans le processus, alors elle garde au plus 10 000 conversations, chacune un jour après son dernier message, sauf autre réglage. Une conversation oubliée ne restaure plus ses jetons. Pourquoi : un serveur qui tourne des semaines ne doit pas garder toutes les valeurs qu'il a vues.

Pour une réponse affichée au fil de l'eau, voir [Afficher une réponse streamée](afficher-une-reponse-streamee.md).

### Ce que voit l'utilisateur final

Une conversation lisible, avec les vraies valeurs. Après un effacement, ou après un jour d'inactivité avec la mémoire en processus, une ancienne réponse affichée de nouveau montre des jetons si l'application la restaure une seconde fois.

### Questions fréquentes

**L'appel s'arrête avec `No thread_id in the LangGraph config`.** L'application ne nomme pas la conversation (BR-CONV-03). Faites-lui passer un identifiant, ou `default` si les conversations n'ont pas besoin d'être séparées.

**Une réponse a affiché le nom d'une autre personne.** Un message ancien a probablement été corrigé à la main (BR-CONV-07), ou la mémoire d'un message a expiré (voir Pièges). Vérifiez l'historique de la conversation.

**« Lyon » n'est pas masqué alors que l'utilisateur l'a écrit.** L'assistant l'avait cité avant lui (BR-CONV-04). Pour forcer le masquage, voir [Imposer une liste blanche et une liste noire](imposer-une-liste-blanche-et-noire.md).

**La réponse s'arrête avec `Deanonymized text holds tokens the pipeline never issued`.** Le modèle a écrit un jeton inconnu (BR-CONV-06). Il a souvent recopié un jeton d'une autre conversation ou d'un document.

**La réponse montre `<<PERSON:1>>` après une longue pause.** La mémoire en processus a oublié la conversation après un jour d'inactivité (BR-CONV-11), ou la conversation a été effacée (BR-CONV-09).

## Pour les développeurs

### Où vivent les règles

| Règle | Emplacement |
|---|---|
| BR-CONV-01, BR-CONV-07 | `src/piighost/pipeline/thread.py:289-339` (`_thread_tokens` sur l'union des détections), `components/placeholder/base.py:145-156` |
| BR-CONV-02 | `conversation_memory/memory.py` (stockage par `thread_id`), `pipeline/thread.py:219-231` (`deanonymize`) |
| BR-CONV-03 | `integrations/langchain/middleware.py:47-66` (`_thread_id`), `integrations/claude_code/hooks.py:101-105`, `piighost-api` (`app.py`, `thread_id` requis sur les routes de fil) |
| BR-CONV-04 | `pipeline/thread.py:322-329`, `conversation_memory/memory.py` (`get_provenance`), `integrations/langchain/middleware.py:370` (`_message_role`) |
| BR-CONV-05 | `pipeline/thread.py:219-231` (`deanonymize`) |
| BR-CONV-06 | `integrations/_deidentify.py:133-155` (`_handle_invented`) |
| BR-CONV-07 | `pipeline/thread.py:190-217` (`anonymize_corrected`), rendu par message lignes 159-178 |
| BR-CONV-08 | `pipeline/thread.py:264-287` (`_detect`) |
| BR-CONV-09 | `pipeline/thread.py:244-262` (`forget_thread`) |
| BR-CONV-10 | `conversation_memory/redis_backend.py` |
| BR-CONV-11 | `conversation_memory/memory.py:13-25` (`DEFAULT_MAX_THREADS`, `DEFAULT_TTL`), `config/models/memory.py` (`InMemoryConfig`) |

Composants liés : `ThreadAnonymizationPipeline`, `AnyConversationMemory` (`remember`, `get_detections`, `get_provenance`, `forget`), `MessageRole`, `Forgotten`, `thread_token_map`, `TextDeidentifier`, `DEFAULT_THREAD_ID` (`conversation_memory/base.py:31`), `MissingThreadIdError`, `InventedPlaceholderStrategy`, `EntityCreateByAssistantStrategy`.

Mécanique : les jetons sont attribués sur l'union des détections de tous les messages, dans l'ordre de première apparition. Le rendu ne remplace que les positions du message courant, car les détections de messages différents partagent le même espace de positions.

### Corriger un message à la main

1. Construisez le jeu corrigé de `Detection` pour le texte exact du message.
2. Appelez `await pipeline.anonymize_corrected(texte, thread_id, détections)`.
3. Si le message corrigé n'est pas le dernier, relancez les tours suivants (BR-CONV-07).

#### Vérifier

```bash
uv run pytest tests/pipeline/test_thread.py tests/pipeline/test_thread_hitl.py tests/acceptance
```

Après la correction, `await pipeline.thread_token_map(thread_id)` doit montrer la correspondance attendue jeton par jeton.

### Pièges

- **Aucune intégration ne retombe sur `default`.** Le middleware LangChain et les hooks Claude Code lèvent `MissingThreadIdError`, le serveur répond 400. Seule la commande `piighost anonymize` garde `--thread-id default`, pour une commande isolée.
- **La numérotation dépend de l'ordre de l'union.** Tout ce qui retire un message ancien de l'union la décale : une correction (BR-CONV-07), mais aussi, d'après le code, l'expiration d'un message Redis avec `ttl` (`conversation_memory/redis_backend.py:200-228`). [à vérifier] : ce second cas n'a pas été rejoué. Pour trancher, écrivez deux messages dans un fil Redis avec un `ttl` court, laissez expirer le premier, puis comparez `thread_token_map`.
- **La mémoire en processus oublie en silence.** Une conversation évincée ou expirée (BR-CONV-11) ne lève rien : ses jetons restent tels quels à la restauration. `max_threads=None` et `ttl=None` lèvent les bornes.
- **La provenance porte sur la clé de valeur** (`value_key`), donc sur toutes les graphies d'une valeur.
- **Le cache de jetons est mémorisé par processus** (256 cartes au plus, `_TOKEN_MEMO_MAX`). Voir [Stocker les conversations](../exploitation/stockage-et-chiffrement.md) pour l'effet sur l'effacement en multi-processus.
- **`anonymize_corrected` ne résout pas les chevauchements** et ne relance pas l'expansion. Le jeu corrigé doit être propre. Il passe seulement par la liste blanche et la liste noire.

### Écarts doc / code

Aucun écart constaté sur cette page.

### Tests

| Test | Couvre |
|---|---|
| `tests/pipeline/test_thread.py` | Jeton stable, numéro suivant, isolement des fils, cache, effacement et mémo, provenance assistant, contrôle final, durée du mémo |
| `tests/pipeline/test_thread_hitl.py` | Ajout et retrait par correction, correction locale au message, correction remplacée |
| `tests/integrations/langchain/test_middleware.py` (`TestThreadId`), `tests/integrations/test_claude_code_hooks.py` | Refus d'un appel sans identifiant (AT-DEV-10-1, AT-DEV-10-2) |
| `tests/conversation_memory/test_in_memory.py` (`TestBounding`) | Bornes par défaut de la mémoire en processus (AT-OPS-7-1) |
| `tests/acceptance/test_dev.py`, `test_dpo.py`, `test_ops.py` | Restauration limitée à sa conversation (AT-DEV-3-2), effacement (AT-DPO-6-1), deux instances sur un même Redis (AT-OPS-2-1) |
| `tests/integrations/test_deidentify.py` | Jetons inventés |

Non couvert : la renumérotation après une correction d'un message ancien (BR-CONV-07). Ce comportement a été constaté en lançant le pipeline, et aucun test ne le fige ni ne l'interdit.
