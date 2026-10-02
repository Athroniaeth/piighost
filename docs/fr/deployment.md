---
icon: lucide/container
---

# Déployer un pipeline en production

Ce guide met en place un pipeline de conversation pour la production, avec une mémoire de conversation Redis qui persiste entre les redémarrages et les workers, chiffre chaque valeur stockée, et lit ses secrets dans l'environnement. Si un seul processus vous suffit et que rien ne doit survivre à sa sortie, la mémoire en RAM convient et vous pouvez passer directement à [Pipeline conversationnel](getting-started/conversation.md).

Le pipeline lit sa forme dans un fichier de configuration. Le déploiement porte donc un fichier TOML et une poignée de variables d'environnement. Aucun code de pipeline n'est écrit à la main.

## Installer les extras

La mémoire Redis tire trois extras au-delà de la couche de configuration, plus un pour le hasher Argon2 utilisé plus bas.

```bash
uv add 'piighost[config,redis,crypto,argon2]'
```

L'extra `config` lit le fichier, `redis` parle au store, `crypto` fournit le cipher AES-GCM, et `argon2` fournit le hasher Argon2id. Retirez `argon2` si vous clez les messages en HMAC-SHA256 à la place.

## Écrire le fichier de configuration

Une section `[memory]` transforme le pipeline en pipeline de conversation gardant un état par conversation. Son `type = "redis"` nomme le store, `[memory.hasher]` cle chaque message dans sa clé de stockage, et `[memory.cipher]` chiffre chaque valeur stockée.

```toml title="pipeline.toml"
--8<-- "snippets/redis_pipeline.toml"
```

`namespace` préfixe chaque clé pour que `piighost` partage une instance Redis avec d'autres applications sans collision. `ttl` est le nombre de secondes qu'un message stocké vit avant que Redis ne l'évince, ou vous l'omettez pour garder les entrées jusqu'à ce que le store décide de les supprimer. `label_counter` émet `<<PERSON:1>>`{ .placeholder }, un jeton qui porte l'identité, ce dont le [middleware](getting-started/langchain.md) a besoin pour restaurer la valeur.

Le catalogue complet des sections, chaque `type` de composant, et la forme JSON du même fichier se trouvent dans la [référence de configuration](configuration/toml.md).

## Poser les secrets dans l'environnement

Le pepper du hasher et la clé du cipher sont des secrets lus dans l'environnement au build, jamais dans le fichier. Un fichier contenant un secret le laisserait fuiter par le versioning.

```bash
export PIIGHOST_HASH_PEPPER="a-long-random-string"
export PIIGHOST_CIPHER_KEY="$(openssl rand -base64 32)"
```

`PIIGHOST_HASH_PEPPER` est n'importe quelle chaîne non vide. `PIIGHOST_CIPHER_KEY` est le base64 de 16, 24 ou 32 octets, donc `openssl rand -base64 32` donne une clé AES-256. Si un [guard de modération](configuration/toml.md) est configuré, son `MISTRAL_API_KEY` suit la même règle et ne vit que dans l'environnement.

!!! warning
    Un pepper ou une clé écrite dans le fichier de configuration annule la protection. Le store fuit alors avec le fichier qui le déchiffre. Gardez les deux dans l'environnement du processus ou dans un gestionnaire de secrets, et faites-les tourner comme n'importe quel identifiant de production. Un secret manquant ou mal formé lève `ConfigError` au build, si bien que le pipeline refuse de démarrer plutôt que de tourner sans protection.

## Charger et exécuter

`load_thread_pipeline` lit le fichier, construit chaque composant, et renvoie le pipeline de conversation. Il lève `ConfigError` si le fichier ne déclare pas de `[memory]`, de sorte qu'une configuration sans état ne peut pas être chargée ici par erreur.

```python
--8<-- "snippets/redis_run.py:example"
```

Le `thread_id` cadre la conversation. La même valeur dans un message ultérieur de `user-42` garde son jeton, et un autre `thread_id` ne la voit jamais, ce qui isole deux utilisateurs. En coulisses le pipeline hache le message en une clé Redis et stocke les détections chiffrées, si bien qu'une fuite du disque Redis ne révèle ni le message ni les données confidentielles.

## Borner le store in-process

Le `InMemoryConversationMemory` par défaut garde chaque conversation dans un dict local au processus, borné à 10 000 conversations et un jour d'inactivité, pour qu'un processus de longue durée qui n'appelle jamais `forget_thread` ne garde pas toutes les valeurs qu'il a vues. Ajustez `max_threads` pour plafonner le nombre de conversations gardées, en évinçant la moins récemment utilisée au-delà, et `ttl` pour expirer une conversation ce nombre de secondes après sa dernière écriture, retirée paresseusement au prochain accès.

```toml title="pipeline.toml"
[memory]
type = "in_memory"
max_threads = 10000
ttl = 3600
```

Pour un déploiement durable ou multi-worker, utilisez plutôt un backend persistant, et oubliez une conversation avec `forget_thread` quand elle se termine.

## Comment le store protège la donnée

Deux protections se combinent à chaque écriture, toutes deux clées par un secret que le store ne détient jamais.

- La **clé est hachée**. Le hasher dérive un digest du message sous le pepper. `argon2` (Argon2id) est lent et memory-hard, le bon choix quand le pepper lui-même peut fuiter. `sha256` (HMAC-SHA256) est rapide et convient à un hot-path chargé. Les deux sont déterministes, donc le même message tombe toujours sur la même clé.
- La **valeur est chiffrée**. `aesgcm` (AES-GCM) chiffre les détections avant écriture, avec un nonce neuf par message. Le déchiffrement échoue sur un ciphertext altéré, donc une altération est détectée.

Le `thread_id` reste en clair comme namespace de clé, ce qui permet d'énumérer et d'oublier toute une conversation avec `forget_thread`. Le modèle de menace et la comparaison des backends sont dans [Sécurité](security.md).

## Utiliser une base SQL à la place

Si votre stack exécute déjà PostgreSQL, `type = "sqlalchemy"` offre le même store durable et multi-worker sur n'importe quel driver SQLAlchemy async. Installez `piighost[config,sqlalchemy,crypto,argon2]`, et pointez la config vers une variable d'environnement pour l'URL, afin que le mot de passe reste hors du fichier.

```toml title="pipeline.toml"
[memory]
type = "sqlalchemy"
url_env = "PIIGHOST_DATABASE_URL"

[memory.hasher]
type = "argon2"

[memory.cipher]
type = "aesgcm"
```

```bash
export PIIGHOST_DATABASE_URL="postgresql+asyncpg://user:pass@db.internal/piighost"
```

L'URL doit utiliser un driver async (`postgresql+asyncpg://...`, `sqlite+aiosqlite://...`). Créez la table une fois au démarrage avec `await pipeline.memory.create_schema()`. Le hacheur et le cipher protègent les valeurs stockées exactement comme pour Redis.

## Le servir en HTTP avec `piighost-api`

Si plusieurs applications partagent le pipeline, ou si une application qui n'est pas écrite en Python en a besoin, servez le même fichier avec `piighost-api`, le serveur compagnon. Son image Docker est `ghcr.io/athroniaeth/piighost-api`. Un premier serveur hors Docker est construit pas à pas dans [Déployer une API de dé-identification](getting-started/api-server.md).

```yaml title="compose.yaml"
services:
  piighost-api:
    image: ghcr.io/athroniaeth/piighost-api:latest
    ports:
      - "8000:8000"
    environment:
      - PIIGHOST_CONFIG=/app/pipeline.toml
      - API_KEY_DEFAULT=${API_KEY_DEFAULT}
      - SECRET_PEPPER=${SECRET_PEPPER}
      - PIIGHOST_HASH_PEPPER=${PIIGHOST_HASH_PEPPER}
      - PIIGHOST_CIPHER_KEY=${PIIGHOST_CIPHER_KEY}
      - EXTRA_PACKAGES=piighost[crypto]
    volumes:
      - ./pipeline.toml:/app/pipeline.toml
      - cache:/root/.cache
    depends_on:
      - redis

  redis:
    image: redis:7-alpine

volumes:
  cache:
```

Le `pipeline.toml` monté est le fichier ci-dessus, avec son `url` posée à `redis://redis:6379/0`, l'adresse du service `redis`. `API_KEY_DEFAULT` porte une clé imprimée par `keyshield generate`, et le serveur refuse de démarrer sans clé. L'image embarque le client Redis et le hacheur Argon2, et `EXTRA_PACKAGES` ajoute le cipher AES-GCM. Le volume `cache` garde les téléchargements du hub, les poids du modèle et les paquets de `EXTRA_PACKAGES` d'un redémarrage de conteneur à l'autre.

L'image lit ces variables :

| Variable | Défaut | Effet |
|---|---|---|
| `PIIGHOST_CONFIG` | `/app/pipeline.toml` | Le fichier de config ou la référence du hub à servir. L'image embarque une config par défaut, tous les groupes de regex du hub, qu'un fichier monté ou une référence du hub remplace |
| `API_HOST` | `0.0.0.0` | Hôte d'écoute |
| `API_PORT` | `8000` | Port d'écoute |
| `LOG_LEVEL` | `info` | Niveau de log |
| `EXTRA_PACKAGES` | vide | Paquets installés avec `uv pip install` au démarrage du conteneur, comme `piighost[gliner2]` pour une configuration qui exécute GLiNER2 |

Pour servir une configuration du hub plutôt qu'un fichier, posez `PIIGHOST_CONFIG` à sa référence et ajoutez la mémoire Redis avec une variable `PIIGHOST_MEMORY`, comme le montre [CLI du serveur](reference/api-cli.md). Chaque conteneur exécute un seul processus serveur, donc passez à l'échelle en ajoutant des conteneurs sur la même mémoire Redis. Chaque route, proxys compris, est listée dans [Endpoints de l'API](reference/api-endpoints.md).

## Voir aussi

- [Référence de configuration](configuration/toml.md) : chaque section et chaque `type` de composant, en TOML et en JSON.
- [Déploiement multi-instance](multi-instance.md) : pourquoi la mémoire Redis partagée est requise derrière un load balancer.
- [Sécurité](security.md) : le modèle de menace au repos et la comparaison des backends.
- [Pipeline conversationnel](getting-started/conversation.md) : l'API du pipeline de conversation que le middleware pilote.
- [Stocker les conversations et protéger les traces](../../openwiki/exploitation/stockage-et-chiffrement.md) : les règles de stockage, de `BR-STO-01` à `BR-STO-08`, écrites pour un DPO ou un exploitant.
