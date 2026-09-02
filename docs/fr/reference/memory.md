---
icon: lucide/database
tags:
  - Memory
---

# Référence de la mémoire de conversation

Module : `piighost.conversation_memory`

Une mémoire de conversation stocke, par thread, les détections trouvées dans chaque message. Un `ThreadAnonymizationPipeline` lit ce store pour garder un seul placeholder par valeur sur toute une conversation : un nom vu tôt se relit comme le même token plus tard, à n'importe quel tour. Chaque backend satisfait le port `AnyConversationMemory`, donc le pipeline traite un dict en mémoire et une base partagée de la même façon.

```python
from piighost.conversation_memory import (
    InMemoryConversationMemory,
    RedisConversationMemory,
    SqlAlchemyConversationMemory,
)
```

`RedisConversationMemory` et `SqlAlchemyConversationMemory` sont exposés paresseusement : importer l'un sans son extra installé lève `ImportError` avec la commande d'installation.

## Le port `AnyConversationMemory`

Quatre méthodes async composent l'interface. Un backend les implémente toutes les quatre, quel que soit le support de stockage.

| Méthode | Rôle |
|---------|------|
| `remember(thread_id, message, detections, role=MessageRole.USER)` | Met en cache les détections trouvées dans un message, en remplaçant toute entrée précédente. |
| `get_detections(thread_id, message=None)` | Renvoie les détections d'un thread pour un message, ou tout le thread comme union dans l'ordre de première apparition quand `message` est omis. |
| `get_provenance(thread_id)` | Renvoie, par valeur, le rôle de sa première apparition dans le thread (valeur casefoldée → `MessageRole`). |
| `forget(thread_id)` | Efface un thread et rapporte un compte `Forgotten` des messages et détections supprimés. |

Le pipeline pilote ces méthodes pour vous. Vous appelez la mémoire directement seulement pour pré-remplir ou inspecter un thread, et `create_schema()` sur le backend SQL au démarrage.

## `InMemoryConversationMemory`

```python
InMemoryConversationMemory(max_threads: int | None = None, ttl: float | None = None)
```

Un cache par thread local au processus dans un dict. Il convient au développement, aux tests et aux déploiements mono-processus. Rien ne survit à un redémarrage et rien n'est partagé entre workers, donc derrière un load balancer deux workers numérotent la même valeur différemment. Il ne requiert aucun extra et c'est le défaut quand un `ThreadAnonymizationPipeline` est construit sans mémoire.

Laissé non défini, le store grossit sans limite jusqu'à ce que `forget_thread` soit appelé, donc bornez-le ou oubliez des threads dans un processus longue durée. `max_threads` évince le thread le moins récemment utilisé. `ttl` fait expirer un thread inactif, paresseusement, au prochain accès.

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

Un stockage persistant et multi-worker. Chaque worker pointé vers le même Redis lit la même numérotation, donc les tokens restent cohérents derrière un load balancer. `namespace` préfixe chaque clé, et `ttl` est le nombre de secondes de vie d'un message avant éviction, ou omis pour le garder jusqu'à ce que Redis le supprime. Requiert `piighost[redis]`.

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
