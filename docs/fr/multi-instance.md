---
icon: lucide/network
---

# Déploiement multi-instance

Un pipeline de thread garde un placeholder par valeur pour toute la durée d'une conversation, si bien qu'un nom vu tôt se relit comme le même token plus tard. Cette cohérence dépend de l'endroit où vit la mémoire de conversation. La mémoire par défaut `InMemoryConversationMemory` est locale au processus, donc deux workers derrière un load balancer numérotent la même valeur différemment en pleine conversation. Une mémoire Redis partagée corrige ce défaut.

!!! note "Résumé"
    `InMemoryConversationMemory` garde les détections de chaque thread dans un dictionnaire de processus. Derrière un load balancer, le même `thread_id` routé vers deux workers verra `Patrick`{ .pii } tokenisé en `<<PERSON:1>>`{ .placeholder } sur un worker et `<<PERSON:2>>`{ .placeholder } sur l'autre, et le LLM ne peut plus relier les deux. La parade est `RedisConversationMemory`, partagée par tous les workers.

## Pourquoi un seul processus ne suffit pas

`InMemoryConversationMemory` garde les détections de chaque thread dans un dictionnaire qui vit dans un seul processus. Elle convient au développement, aux tests, et à un déploiement mono-processus. Rien ne survit à un redémarrage et rien n'est partagé entre processus. Elle peut être bornée avec `max_threads` et `ttl` pour plafonner sa croissance, mais un déploiement multi-worker a toujours besoin d'un backend partagé.

Le problème apparaît dès qu'un load balancer route le même `thread_id` vers plus d'un worker. Chaque worker tient sa propre mémoire, et ces mémoires ne se parlent pas. Une valeur tokenisée en `<<PERSON:1>>`{ .placeholder } sur le worker A est inconnue du worker B, qui la numérote à neuf.

```text
Turn 1 (routed to worker A)
  worker A memory: { Patrick -> <<PERSON:1>> }
  worker B memory: {}

Turn 2 (routed to worker B, "Patrick" still in the context)
  worker B memory: { Patrick -> <<PERSON:1>> }   # numbered fresh, may collide

Turn 3 (worker B sees "Marie")
  worker B memory: { Patrick -> <<PERSON:1>>, Marie -> <<PERSON:2>> }

Turn 4 (worker A sees "Marie", numbers from its own state)
  worker A memory: { Patrick -> <<PERSON:1>>, Marie -> <<PERSON:2>> }
  # Marie could have taken another number if a different PII had preceded it on A.
```

La panne est silencieuse. Aucune exception n'est levée, le pipeline produit un texte tokenisé valide, et l'incohérence n'apparaît que dans les réponses du LLM, qui perd le fil entre les tours parce que la même personne porte désormais deux noms.

## Configurer une mémoire Redis partagée

Pointez tous les workers sur une seule instance Redis. Les tokens sont attribués sur l'union des détections d'un thread, et cette union vit dans Redis, donc tous les workers lisent la même numérotation. Le `thread_id` reste l'unité d'isolation, de sorte que deux utilisateurs ne partagent jamais un token.

```toml title="pipeline.toml"
[detector]
type = "regex"
catalogs = ["generic"]

[linker]
type = "exact"

[anonymizer.placeholder]
type = "label_counter"

[memory]
type = "redis"
url = "redis://redis.internal:6379/0"
namespace = "piighost"
ttl = 3600

[memory.hasher]
type = "argon2"

[memory.cipher]
type = "aesgcm"
```

```python
from piighost.config import load_thread_pipeline

pipeline = load_thread_pipeline("pipeline.toml")
```

Le cas du tour 2 se résout maintenant dans l'autre sens. Le worker B lit `Patrick -> <<PERSON:1>>`{ .placeholder } directement dans Redis et le garde, parce que le store où le worker A a écrit est le store que le worker B lit. Tout worker qui reprend la conversation reproduit le même token pour la même valeur.

Le backend Redis peut chiffrer chaque valeur stockée et hacher chaque clé. Cette protection est optionnelle et tout ou rien, donc la config montrée ci-dessus, qui définit à la fois un hacheur et un cipher, en bénéficie, et lit son pepper et sa clé de cipher dans l'environnement. Ces secrets et la mise en place complète sont traités dans [Déployer un pipeline en production](deployment.md), et chaque clé `[memory]` est dans la [référence de configuration](configuration/toml.md).

Une base SQL est l'autre store partagé. `type = "sqlalchemy"` offre la même cohérence entre workers, adossée à PostgreSQL (ou n'importe quel driver SQLAlchemy async), ce qui convient à une stack qui exécute déjà une base relationnelle et veut que la correspondance des tokens survive durablement aux redémarrages. Il lit l'URL de la base dans `PIIGHOST_DATABASE_URL` et prend le même hacheur et le même cipher optionnels que Redis.

```toml
[memory]
type = "sqlalchemy"
url_env = "PIIGHOST_DATABASE_URL"

[memory.hasher]
type = "argon2"

[memory.cipher]
type = "aesgcm"
```

## Borner le mémo de tokens sur chaque worker

Une mémoire partagée règle la numérotation, mais chaque worker mémoïse aussi la carte de tokens qu'il dérive, indexée sur l'état du thread qu'il a lu. Ce mémo garde les valeurs du thread en clair, et `forget_thread` n'atteint que le mémo du processus où il tourne. Une demande d'effacement routée vers le worker A laisse donc la copie du worker B debout jusqu'à ce que sa borne de taille l'évince.

Rien de périmé n'est jamais servi : la clé du mémo porte l'union relue du store, que l'effacement a vidée, donc le worker B recalcule et ne trouve rien. Le problème est la rétention, pas la correction. `token_memo_ttl` la borne sans aucun message inter-worker à perdre :

```toml
token_memo_ttl = 300.0

[memory]
type = "redis"
url = "redis://localhost:6379/0"
```

C'est un scalaire de premier niveau, il se place donc au-dessus de la première section. Cinq minutes est un point de départ raisonnable, assez long pour qu'une conversation vivante continue de toucher le mémo, assez court pour que les valeurs d'un thread oublié ne s'attardent pas.

Le balayage suit le trafic du worker où il tourne, une entrée tombe à la prochaine dérivation d'une carte de tokens par ce worker, pas sur une horloge. Un worker qui devient inactif juste après un effacement garde donc sa copie jusqu'à sa requête suivante, ou jusqu'à la fin du processus. Borner cela demanderait une tâche de fond, qu'une librairie n'a pas à lancer, donc le TTL borne les workers actifs et la durée de vie du processus borne les inactifs. Laissée vide, une entrée vit jusqu'à ce que 256 autres la poussent dehors, ce qui sur un worker peu sollicité peut durer.

## S'aligner sur LangGraph

Le même piège frappe le `checkpointer` de LangGraph. `MemorySaver` est local au processus, `PostgresSaver` et `RedisSaver` sont partagés. Si votre agent fait déjà tourner un saver partagé derrière le load balancer, faites tourner la mémoire de `piighost` sur la même infrastructure. Un `thread_id` qui a un état checkpointé a alors aussi son mapping de tokens joignable, sur n'importe quel worker.

## Voir aussi

- [Déployer un pipeline en production](deployment.md) : la mise en place Redis complète, les extras et les secrets.
- [Référence de configuration](configuration/toml.md) : chaque clé `[memory]`, en TOML et en JSON.
- [Sécurité](security.md) : les garanties au repos du backend Redis et la comparaison des backends.
- [Pipeline conversationnel](getting-started/conversation.md) : comment les tokens restent cohérents sur un thread.
