---
icon: lucide/network
---

# Déploiement multi-instance

Un pipeline de conversation garde un placeholder par valeur pour toute la durée d'une conversation, si bien qu'un nom vu tôt se relit comme le même jeton plus tard. Cette cohérence dépend de l'endroit où vit la mémoire de conversation. La mémoire par défaut, `InMemoryConversationMemory`, est locale au processus. Deux workers derrière un répartiteur de charge numérotent donc la même valeur différemment en pleine conversation. Une mémoire Redis partagée corrige ce défaut.

## Pourquoi un seul processus ne suffit pas

`InMemoryConversationMemory` garde les détections de chaque conversation dans un dictionnaire qui vit dans un seul processus. Elle convient au développement, aux tests, et à un déploiement mono-processus. Rien ne survit à un redémarrage et rien n'est partagé entre processus. Elle est bornée par défaut, et `max_threads` et `ttl` règlent sa croissance. Un déploiement multi-worker a pourtant toujours besoin d'un backend partagé.

Le problème apparaît dès qu'un répartiteur de charge envoie le même `thread_id` vers plus d'un worker. Chaque worker tient sa propre mémoire, et ces mémoires ne se parlent pas. Une valeur remplacée par `<<PERSON:1>>`{ .placeholder } sur le worker A est inconnue du worker B, qui numérote à partir de zéro.

```text
Turn 1, routed to worker A: "Patrick called."
  worker A memory: { Patrick -> <<PERSON:1>> }
  worker B memory: {}

Turn 2, routed to worker B: "Marie called back."
  worker A memory: { Patrick -> <<PERSON:1>> }
  worker B memory: { Marie -> <<PERSON:1>> }

Turn 3, routed to worker A: "Patrick and Marie met."
  worker A memory: { Patrick -> <<PERSON:1>>, Marie -> <<PERSON:2>> }
  worker B memory: { Marie -> <<PERSON:1>> }
```

Le LLM reçoit `<<PERSON:1>>`{ .placeholder } pour `Patrick`{ .pii } au tour 1, puis pour `Marie`{ .pii } au tour 2. Au tour 3, `Marie`{ .pii } devient `<<PERSON:2>>`{ .placeholder }. Le même jeton désigne deux personnes, et la même personne porte deux jetons.

La panne est silencieuse. Aucune exception n'est levée, et le pipeline produit un texte dé-identifié valide. L'incohérence n'apparaît que dans les réponses du LLM. Le LLM perd le fil entre les tours, parce que les jetons ne désignent plus les mêmes personnes.

## Configurer une mémoire Redis partagée

Pointez tous les workers sur une seule instance Redis. Les jetons sont attribués sur l'union des détections d'une conversation. Cette union vit dans Redis, donc tous les workers lisent la même numérotation. Le `thread_id` reste l'unité d'isolation, de sorte que deux utilisateurs ne partagent jamais un jeton.

```toml title="pipeline.toml"
--8<-- "snippets/redis_pipeline.toml"
```

```python
--8<-- "snippets/redis_load.py:example"
```

Avec Redis, le tour 2 se passe autrement. Le worker B lit la mémoire que le worker A a écrite au tour 1. `<<PERSON:1>>`{ .placeholder } y est déjà attribué à `Patrick`{ .pii }, donc `Marie`{ .pii } reçoit `<<PERSON:2>>`{ .placeholder }. Tout worker qui reprend la conversation reproduit le même jeton pour la même valeur.

## Vérifier que les workers s'accordent

Construisez deux pipelines depuis le même fichier, un par worker, et envoyez une même conversation à chacun. Chaque pipeline garde son propre cache de processus. Seul le Redis partagé peut donc amener le second pipeline à réutiliser les jetons du premier.

```python
--8<-- "snippets/redis_two_workers.py:example"
```

La sortie doit être :

```text
--8<-- "snippets/redis_two_workers.out"
```

`bob@corp.com`{ .pii }, nouveau dans la conversation, prend `<<EMAIL:2>>`{ .placeholder }. `alice@corp.com`{ .pii } garde le `<<EMAIL:1>>`{ .placeholder } que le worker A lui a donné. Sans la mémoire partagée, le worker B numéroterait son message depuis zéro et donnerait `<<EMAIL:1>>`{ .placeholder } à Bob. En production, faites la même vérification sur deux processus workers derrière le répartiteur de charge.

Le backend Redis peut chiffrer chaque valeur stockée et hacher chaque clé. Cette protection est optionnelle et tout ou rien. La config montrée ci-dessus définit à la fois un hacheur et un cipher, donc elle en bénéficie. Elle lit son pepper et sa clé de cipher dans l'environnement. Ces secrets et la mise en place complète sont traités dans [Déploiement](deployment.md). Chaque clé `[memory]` est dans la [référence de configuration](configuration/toml.md).

Une base SQL est l'autre stockage partagé. `type = "sqlalchemy"` offre la même cohérence entre workers, adossée à PostgreSQL (ou n'importe quel driver SQLAlchemy async). Ce backend convient à une stack qui exécute déjà une base relationnelle et veut que la correspondance des jetons survive durablement aux redémarrages. Il lit l'URL de la base dans `PIIGHOST_DATABASE_URL` et prend le même hacheur et le même cipher optionnels que Redis.

```toml
[memory]
type = "sqlalchemy"
url_env = "PIIGHOST_DATABASE_URL"

[memory.hasher]
type = "argon2"

[memory.cipher]
type = "aesgcm"
```

## Borner le mémo de jetons sur chaque worker

Une mémoire partagée règle la numérotation. Mais chaque worker mémoïse aussi la carte de jetons qu'il dérive, c'est-à-dire qu'il la garde dans un cache local, le mémo. Ce mémo est indexé sur l'état de la conversation que le worker a lu. Il garde les valeurs de la conversation en clair, et `forget_thread` n'atteint que le mémo du processus où il tourne. Une demande d'effacement routée vers le worker A laisse donc la copie du worker B debout jusqu'à ce que sa borne de taille l'évince.

Rien de périmé n'est jamais servi, parce que la clé du mémo porte l'union relue dans le stockage. L'effacement a vidé cette union, donc le worker B recalcule et ne trouve rien. Le problème est la rétention, pas l'exactitude. `token_memo_ttl` borne cette rétention sans aucun message entre workers, donc sans message qui puisse se perdre :

```toml
token_memo_ttl = 300.0

[memory]
type = "redis"
url = "redis://localhost:6379/0"
```

C'est un scalaire de premier niveau, il se place donc au-dessus de la première section. Cinq minutes est un point de départ raisonnable, assez long pour qu'une conversation vivante continue de toucher le mémo, assez court pour que les valeurs d'une conversation oubliée ne s'attardent pas.

Le balayage suit le trafic du worker où il tourne, pas une horloge. Une entrée tombe la prochaine fois que ce worker dérive une carte de jetons. Un worker qui devient inactif juste après un effacement garde donc sa copie jusqu'à sa requête suivante, ou jusqu'à la fin du processus. Borner ce cas demanderait une tâche de fond, et une librairie n'a pas à en lancer. Le TTL borne donc les workers actifs, et la durée de vie du processus borne les inactifs. Si le TTL n'est pas défini, une entrée vit jusqu'à ce que 256 autres la poussent dehors. Sur un worker peu sollicité, cette éviction peut tarder.

## S'aligner sur LangGraph

Le même piège frappe le `checkpointer` de LangGraph. `MemorySaver` est local au processus, `PostgresSaver` et `RedisSaver` sont partagés. Si votre agent fait déjà tourner un saver partagé derrière le répartiteur de charge, faites tourner la mémoire de `piighost` sur la même infrastructure. Sur n'importe quel worker, un `thread_id` qui a un état checkpointé retrouve alors aussi sa correspondance de jetons.

## Voir aussi

- [Déploiement](deployment.md) : la mise en place Redis complète, les extras et les secrets.
- [Référence de configuration](configuration/toml.md) : chaque clé `[memory]`, en TOML et en JSON.
- [Sécurité](security.md) : les garanties au repos du backend Redis et la comparaison des backends.
- [Pipeline conversationnel](getting-started/conversation.md) : comment les jetons restent cohérents sur une conversation.
- [Stocker les conversations et protéger les traces](../../openwiki/fr/operations/storage-and-encryption.md) : les règles de stockage, de `BR-STO-01` à `BR-STO-08`, écrites pour un DPO ou un exploitant.
