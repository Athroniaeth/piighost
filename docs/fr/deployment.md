---
icon: lucide/container
---

# Déployer un pipeline en production

Ce guide met en place un pipeline de thread pour la production, avec une mémoire de conversation Redis qui persiste entre les redémarrages et les workers, chiffre chaque valeur stockée, et lit ses secrets dans l'environnement. Si un seul processus vous suffit et que rien ne doit survivre à sa sortie, la mémoire en RAM convient et vous pouvez passer directement à [Pipeline conversationnel](getting-started/conversation.md).

Le pipeline lit sa forme dans un fichier de configuration. Le déploiement porte donc un fichier TOML et une poignée de variables d'environnement. Aucun code de pipeline n'est écrit à la main.

## Installer les extras

La mémoire Redis tire trois extras au-delà de la couche de configuration, plus un pour le hasher Argon2 utilisé plus bas.

```bash
uv add 'piighost[config,redis,crypto,argon2]'
```

L'extra `config` lit le fichier, `redis` parle au store, `crypto` fournit le cipher AES-GCM, et `argon2` fournit le hasher Argon2id. Retirez `argon2` si vous clez les messages en HMAC-SHA256 à la place.

## Écrire le fichier de configuration

Une section `[memory]` transforme le pipeline en pipeline de thread gardant un état par thread. Son `type = "redis"` nomme le store, `[memory.hasher]` cle chaque message dans sa clé de stockage, et `[memory.cipher]` chiffre chaque valeur stockée.

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

`namespace` préfixe chaque clé pour que `piighost` partage une instance Redis avec d'autres applications sans collision. `ttl` est le nombre de secondes qu'un message stocké vit avant que Redis ne l'évince, ou vous l'omettez pour garder les entrées jusqu'à ce que le store décide de les supprimer. `label_counter` émet `<<PERSON:1>>`{ .placeholder }, un token qui porte l'identité, ce dont le [middleware](getting-started/langchain.md) a besoin pour restaurer la valeur.

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

`load_thread_pipeline` lit le fichier, construit chaque composant, et renvoie le pipeline de thread. Il lève `ConfigError` si le fichier ne déclare pas de `[memory]`, de sorte qu'une configuration sans état ne peut pas être chargée ici par erreur.

```python
from piighost.config import load_thread_pipeline

pipeline = load_thread_pipeline("pipeline.toml")

result = await pipeline.anonymize("Patrick lives in Lyon.", thread_id="user-42")
print(result.text)  # <<PERSON:1>> lives in <<LOCATION:1>>.
```

Le `thread_id` cadre la conversation. La même valeur dans un message ultérieur de `user-42` garde son token, et un autre `thread_id` ne la voit jamais, ce qui isole deux utilisateurs. En coulisses le pipeline hache le message en une clé Redis et stocke les détections chiffrées, si bien qu'une fuite du disque Redis ne révèle ni le message ni la PII.

## Comment le store protège la donnée

Deux protections se combinent à chaque écriture, toutes deux clées par un secret que le store ne détient jamais.

- La **clé est hachée**. Le hasher dérive un digest du message sous le pepper. `argon2` (Argon2id) est lent et memory-hard, le bon choix quand le pepper lui-même peut fuiter. `sha256` (HMAC-SHA256) est rapide et convient à un hot-path chargé. Les deux sont déterministes, donc le même message tombe toujours sur la même clé.
- La **valeur est chiffrée**. `aesgcm` (AES-GCM) chiffre les détections avant écriture, avec un nonce neuf par message. Le déchiffrement échoue sur un ciphertext altéré, donc une altération est détectée.

Le `thread_id` reste en clair comme namespace de clé, ce qui permet d'énumérer et d'oublier tout un thread avec `forget_thread`. Le modèle de menace et la comparaison des backends sont dans [Sécurité](security.md).

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

## Voir aussi

- [Référence de configuration](configuration/toml.md) : chaque section et chaque `type` de composant, en TOML et en JSON.
- [Déploiement multi-instance](multi-instance.md) : pourquoi la mémoire Redis partagée est requise derrière un load balancer.
- [Sécurité](security.md) : le modèle de menace au repos et la comparaison des backends.
- [Pipeline conversationnel](getting-started/conversation.md) : l'API du pipeline de thread que le middleware pilote.
