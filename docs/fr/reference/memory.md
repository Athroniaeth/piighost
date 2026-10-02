---
icon: lucide/database
tags:
  - Mémoire
---

# Référence de la mémoire de conversation

Module : `piighost.conversation_memory`

Une mémoire de conversation stocke, par conversation, les détections trouvées dans chaque message. Un `ThreadAnonymizationPipeline` lit ce store pour garder un seul placeholder par valeur sur toute une conversation, un nom vu tôt se relit comme le même jeton plus tard, à n'importe quel tour. Chaque backend satisfait le port `AnyConversationMemory`, donc le pipeline traite un dict en mémoire et une base partagée de la même façon.

```python
from piighost.conversation_memory import (
    InMemoryConversationMemory,
    RedisConversationMemory,
    SqlAlchemyConversationMemory,
)
```

`RedisConversationMemory` et `SqlAlchemyConversationMemory` sont exposés paresseusement, importer l'un sans son extra installé lève `ImportError` avec la commande d'installation.

## Le port `AnyConversationMemory`

Quatre méthodes async composent l'interface. Un backend les implémente toutes les quatre, quel que soit le support de stockage.

| Méthode | Rôle |
|---------|------|
| `remember(thread_id, message, detections, role=MessageRole.USER)` | Met en cache les détections trouvées dans un message, en remplaçant toute entrée précédente. |
| `get_detections(thread_id, message=None)` | Renvoie les détections d'une conversation pour un message, ou toute la conversation comme union dans l'ordre de première apparition quand `message` est omis. |
| `get_provenance(thread_id)` | Renvoie, par valeur, le rôle de sa première apparition dans la conversation (clé de valeur → `MessageRole`, les mêmes mots quelles que soient leurs espaces et leur casse). |
| `forget(thread_id)` | Efface une conversation et rapporte un compte `Forgotten` des messages et détections supprimés. |

Le pipeline pilote ces méthodes pour vous. Vous appelez la mémoire directement seulement pour pré-remplir ou inspecter une conversation, et `create_schema()` sur le backend SQL au démarrage.

### `Forgotten`

```python
@dataclass(frozen=True, slots=True)
class Forgotten:
    messages: int
    detections: int
```

Ce que `forget` a effacé, rendu comme preuve pour une demande d'effacement. `forget_thread` sur un pipeline de conversation rend le même objet.

| Champ | Type | Signification |
|-------|------|---------------|
| `messages` | `int` | Le nombre de messages en cache supprimés |
| `detections` | `int` | Le nombre de détections supprimées dans ces messages |

## `InMemoryConversationMemory`

```python
InMemoryConversationMemory(
    max_threads: int | None = 10_000,
    ttl: float | None = 86_400.0,
    time_source: Callable[[], float] = time.monotonic,
)
```

Un cache par conversation local au processus dans un dict. Il convient au développement, aux tests et aux déploiements mono-processus. Rien ne survit à un redémarrage et rien n'est partagé entre workers, donc derrière un load balancer deux workers numérotent la même valeur différemment. Il ne requiert aucun extra et c'est le défaut quand un `ThreadAnonymizationPipeline` est construit sans mémoire.

Le store est borné par défaut, à 10 000 conversations (`DEFAULT_MAX_THREADS`) et un jour d'inactivité (`DEFAULT_TTL`). `max_threads` évince la conversation la moins récemment utilisée. `ttl` fait expirer une conversation inactive, paresseusement, au prochain accès, et ses jetons ne sont alors plus restaurés. `None` lève une borne, le store grossit alors jusqu'à ce que `forget_thread` soit appelé. `time_source` est l'horloge que lit `ttl`, injectable pour les tests.

## `RedisConversationMemory`

```python
RedisConversationMemory(
    client: Redis,
    hasher: AnyHasher | None = None,
    cipher: AnyCipher | None = None,
    namespace: str = "piighost",
    ttl: int | None = None,
)
```

Un stockage persistant et multi-worker. Chaque worker pointé vers le même Redis lit la même numérotation, donc les jetons restent cohérents derrière un load balancer. `namespace` préfixe chaque clé, et `ttl` est le nombre de secondes de vie d'un message avant éviction, ou omis pour le garder jusqu'à ce que Redis le supprime. Requiert `piighost[redis]`.

Passez à la fois un `hasher` et un `cipher` pour stocker de façon sécurisée (la clé est hachée sous un pepper, la valeur chiffrée), ou aucun des deux pour stocker en clair. En passer exactement un lève `ValueError`, et une configuration en clair sur un store en réseau émet un `PIIGhostSecurityWarning`.

## `SqlAlchemyConversationMemory`

```python
SqlAlchemyConversationMemory(
    engine: AsyncEngine,
    hasher: AnyHasher | None = None,
    cipher: AnyCipher | None = None,
    table_name: str = "piighost_conversation_messages",
)
```

Un stockage durable et multi-worker sur n'importe quel driver SQLAlchemy async (PostgreSQL via `asyncpg`, SQLite via `aiosqlite`, ...). Il prend un `AsyncEngine` injecté dont vous possédez le cycle de vie. Appelez `await memory.create_schema()` une fois au démarrage pour créer la table de façon idempotente. Le `hasher`/`cipher` suivent la même règle du tout ou rien que Redis. Requiert `piighost[sqlalchemy]`.

## Construire depuis un fichier

La section `[memory]` d'un fichier de config construit n'importe lequel de ces backends, discriminée sur `type` (`in_memory`, `redis`, `sqlalchemy`). Ses clés, les options de hacheur et de cipher, et les variables d'environnement pour les secrets sont dans la [référence de configuration](../configuration/toml.md).

## Voir aussi

- [Référence de configuration](../configuration/toml.md) : chaque clé `[memory]`, en TOML et en JSON.
- [Déploiement multi-instance](../multi-instance.md) : pourquoi un backend partagé est requis derrière un load balancer.
- [Déployer un pipeline en production](../deployment.md) : la mise en place complète Redis et SQL avec les secrets.
- [Sécurité](../security.md) : les garanties au repos et la comparaison des backends.
