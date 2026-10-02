---
type: workflow
title: Suivre une conversation et restaurer la réponse
description: Comment PIIGhost garde le même jeton pour une valeur sur toute une conversation, restaure la réponse du modèle, traite les valeurs apportées par l'assistant et les jetons inventés, applique une correction humaine et efface une conversation.
tags: [thread, conversation-memory, deanonymize, provenance, invented-placeholder, hitl, erasure, streaming]
verified:
  - by: openwiki/0.6.1
    at: 2026-10-01T18:36:49.731Z
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
generated: { by: "claude-code", at: "2026-10-01T18:36:49.731Z" }
---

# Suivre une conversation et restaurer la réponse

## En bref

- Dans une conversation, une même valeur garde le même jeton du premier au dernier message.
- Deux conversations sont isolées : le même nom peut y porter le même numéro sans rien partager.
- Une valeur citée d'abord par l'assistant reste en clair, même si l'utilisateur la reprend ensuite.
- Un jeton que PIIGhost n'a jamais émis est refusé par défaut à la restauration.
- Effacer une conversation supprime sa mémoire. Les jetons de cette conversation ne sont plus restaurés ensuite.

Les termes sont définis dans le [glossaire](../glossaire.md). Le traitement d'un message isolé est décrit dans [Protéger un message avant l'envoi au modèle](proteger-un-message.md).

## Pour le métier

PIIGhost n'a pas d'écran. Une conversation est désignée par un identifiant que l'application transmet à chaque message. Ce que vous pouvez constater, c'est le texte reçu par le modèle et la réponse affichée.

### Exemple de conversation

| Tour | Auteur | Texte écrit | Texte vu par le modèle |
|---|---|---|---|
| 1 | utilisateur | Je suis Claire Dubois. | Je suis `<<PERSON:1>>`. |
| 2 | utilisateur | Mon collègue Marc Petit et Claire Dubois. | Mon collègue `<<PERSON:2>>` et `<<PERSON:1>>`. |
| 3 | assistant | Le siège est à Lyon. | Le siège est à Lyon. |
| 4 | utilisateur | Je vais à Lyon voir Marc Petit. | Je vais à Lyon voir `<<PERSON:2>>`. |

Si le modèle répond « Bonjour `<<PERSON:1>>`, saluez `<<PERSON:2>>`. », l'utilisateur lit « Bonjour Claire Dubois, saluez Marc Petit. »

### Règles à connaître

**RG-FIL-01.** Quand une valeur réapparaît dans un message suivant de la même conversation, alors elle reprend son jeton. Une nouvelle valeur du même type reçoit le numéro suivant.

**RG-FIL-02.** Quand la même valeur apparaît dans deux conversations différentes, alors chacune a sa propre numérotation. Rien ne relie les deux. Exemple : « Marc Petit » est `<<PERSON:2>>` dans une conversation et `<<PERSON:1>>` dans une autre.

**RG-FIL-03.** Quand l'assistant cite le premier une valeur, alors elle reste en clair pour toute la conversation, même reprise par l'utilisateur (tour 4, « Lyon »). Pourquoi : le modèle connaît déjà cette valeur, et la masquer lui retirerait une connaissance utile. Une valeur apportée d'abord par l'utilisateur reste masquée, même si l'assistant la répète.

**RG-FIL-04.** Quand la réponse du modèle contient un jeton de la conversation, alors il est remplacé par la vraie valeur. Un jeton d'une autre conversation n'est pas restauré.

**RG-FIL-05.** Quand la réponse contient un jeton au bon format que PIIGhost n'a jamais émis, alors la restauration est refusée par défaut : `Deanonymized text holds tokens the pipeline never issued: ['<<PERSON:9>>']`. Ce jeton a été inventé par le modèle ou injecté par un texte. Deux autres choix existent : le garder ou le retirer.

**RG-FIL-06.** Quand une personne corrige à la main les valeurs d'un message, alors sa correction remplace le repérage automatique de ce message seulement. Exemple : retirer « Claire Dubois » du tour 1 le laisse en clair au tour 1, et il reste masqué au tour 2.

**RG-FIL-07.** Quand une correction retire ou ajoute une valeur dans un message ancien, alors les numéros peuvent changer pour toute la conversation. Exemple : après le retrait de « Claire Dubois » au tour 1, `<<PERSON:1>>` désigne Marc Petit et `<<PERSON:2>>` Claire Dubois.

> [!WARNING]
> Après une correction, une réponse du modèle qui reprend un ancien jeton peut être restaurée avec le nom d'une autre personne. Dans l'exemple, « Bonjour `<<PERSON:1>>` » devient « Bonjour Marc Petit », alors que le modèle parlait de Claire Dubois. Relancez la conversation à partir du message corrigé.

**RG-FIL-08.** Quand un message identique est renvoyé dans la même conversation, alors son repérage n'est pas refait. Le résultat enregistré la première fois est réutilisé.

**RG-FIL-09.** Quand une conversation est effacée, alors toute sa mémoire est supprimée, et l'effacement rend le nombre de messages et de valeurs supprimés. Exemple : `Forgotten(messages=4, detections=5)` pour la conversation ci-dessus. Ensuite, `<<PERSON:1>>` n'est plus restauré et reste tel quel.

**RG-FIL-10.** Quand la réponse est diffusée au fil de l'eau, alors un jeton coupé entre deux morceaux (« `<<PER` » puis « `SON:1>>` ») est attendu en entier avant d'être restauré, si l'application utilise le décodeur de flux.

### Ce que voit l'utilisateur final

Une conversation lisible, avec les vraies valeurs. Après un effacement, une ancienne réponse affichée de nouveau montre des jetons si l'application la restaure une seconde fois.

### Questions fréquentes

**Une réponse a affiché le nom d'une autre personne.** Un message ancien a probablement été corrigé à la main (RG-FIL-07), ou la mémoire d'un message a expiré (voir Pièges). Vérifiez l'historique de la conversation.

**« Lyon » n'est pas masqué alors que l'utilisateur l'a écrit.** L'assistant l'avait cité avant lui (RG-FIL-03). Pour forcer le masquage, voir [Imposer des valeurs toujours ou jamais masquées](imposer-des-listes-serveur.md).

**La réponse s'arrête avec `Deanonymized text holds tokens the pipeline never issued`.** Le modèle a écrit un jeton inconnu (RG-FIL-05). Il a souvent recopié un jeton d'une autre conversation ou d'un document.

**Après l'effacement d'une conversation, la réponse montre `<<PERSON:1>>`.** C'est l'effet attendu de l'effacement (RG-FIL-09).

## Pour les développeurs

### Où vivent les règles

| Règle | Emplacement |
|---|---|
| RG-FIL-01, RG-FIL-07 | `src/piighost/pipeline/thread.py:289-339` (`_thread_tokens` sur l'union des détections), `components/placeholder/base.py:145-156` |
| RG-FIL-02 | `conversation_memory/memory.py:44-70` (stockage par `thread_id`) |
| RG-FIL-03 | `pipeline/thread.py:322-329`, `conversation_memory/memory.py:91-102` (`get_provenance`) |
| RG-FIL-04 | `pipeline/thread.py:219-231` (`deanonymize`) |
| RG-FIL-05 | `integrations/_deidentify.py:133-155` |
| RG-FIL-06 | `pipeline/thread.py:190-217` (`anonymize_corrected`), rendu par message lignes 159-178 |
| RG-FIL-08 | `pipeline/thread.py:264-287` (`_detect`) |
| RG-FIL-09 | `pipeline/thread.py:244-262` (`forget_thread`) |
| RG-FIL-10 | `components/placeholder/streaming.py`, `integrations/_deidentify.py:83-107` |

Composants liés : `ThreadAnonymizationPipeline`, `AnyConversationMemory` (`remember`, `get_detections`, `get_provenance`, `forget`), `MessageRole`, `Forgotten`, `thread_token_map`, `TextDeidentifier`.

Mécanique : les jetons sont attribués sur l'union des détections de tous les messages, dans l'ordre de première apparition. Le rendu ne remplace que les positions du message courant, car les détections de messages différents partagent le même espace de positions.

### Corriger un message à la main

1. Construisez le jeu corrigé de `Detection` pour le texte exact du message.
2. Appelez `await pipeline.anonymize_corrected(texte, thread_id, détections)`.
3. Si le message corrigé n'est pas le dernier, relancez les tours suivants (RG-FIL-07).

#### Vérifier

```bash
uv run pytest tests/pipeline/test_thread.py tests/pipeline/test_thread_hitl.py
```

Après la correction, `await pipeline.thread_token_map(thread_id)` doit montrer la correspondance attendue jeton par jeton.

### Pièges

- **`thread_id` est obligatoire** sur chaque appel du pipeline de conversation. Il n'y a pas de valeur par défaut à ce niveau. Seules les intégrations retombent sur `default`.
- **La numérotation dépend de l'ordre de l'union.** Tout ce qui retire un message ancien de l'union la décale : une correction (RG-FIL-07), mais aussi, d'après le code, l'expiration d'un message Redis avec `ttl` (`conversation_memory/redis_backend.py:200-228`). [à vérifier] : ce second cas n'a pas été rejoué. Pour trancher, écrivez deux messages dans un fil Redis avec un `ttl` court, laissez expirer le premier, puis comparez `thread_token_map`.
- **La provenance porte sur la clé de valeur** (`value_key`), donc sur toutes les graphies d'une valeur.
- **Le cache de jetons est mémorisé par processus** (256 cartes au plus, `_TOKEN_MEMO_MAX`). Voir [Stocker les conversations](../exploitation/stockage-et-chiffrement.md) pour l'effet sur l'effacement en multi-processus.
- **`anonymize_corrected` ne résout pas les chevauchements** et ne relance pas l'expansion. Le jeu corrigé doit être propre. Il passe seulement par les listes serveur.

### Écarts doc / code

Aucun écart constaté sur cette page.

### Tests

| Test | Couvre |
|---|---|
| `tests/pipeline/test_thread.py` | Jeton stable, numéro suivant, isolement des fils, cache, effacement et mémo, provenance assistant, contrôle final, durée du mémo |
| `tests/pipeline/test_thread_hitl.py` | Ajout et retrait par correction, correction locale au message, correction remplacée |
| `tests/pipeline/test_thread_recognizer.py` | Grammaire des jetons exposée aux intégrations |
| `tests/integrations/test_deidentify.py`, `test_deidentify_stream.py` | Jetons inventés, restauration en flux |

Non couvert : la renumérotation après une correction d'un message ancien (RG-FIL-07). Ce comportement a été constaté en lançant le pipeline, et aucun test ne le fige ni ne l'interdit.
