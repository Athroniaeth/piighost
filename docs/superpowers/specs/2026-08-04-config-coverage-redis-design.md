# Config Coverage C2: Redis Memory and Crypto Design

Design spec for the fourth sub-brick of the config coverage brick of the PIIGhost
v2 rewrite, the Redis conversation backend and its crypto configuration.
Internal design document, French prose, English code identifiers.

## Context

La couverture se découpe en A étapes optionnelles (fait), B détecteurs (fait), C
thread plus mémoire, D client plus JSON. La brique C, trop vaste, a été scindée en
C1, thread plus mémoire in_memory (fait), et C2, backend Redis plus crypto, ce
document.

Le backend RedisConversationMemory persiste la mémoire de conversation dans Redis
pour un déploiement multi-worker. Il chiffre chaque valeur et hache le message en
clé, donc il prend, en plus d'un client Redis, un hasher et un cipher. C2 câble
les trois en config.

Les trois extras concernés, redis, cryptography et argon2, sont présents dans
l'environnement dev, et Redis.from_url ne se connecte pas à la construction, donc
chaque build() est testable de bout en bout hors ligne.

## Goal

Trois nouveaux modèles de config, un HasherConfig sha256 ou argon2, un CipherConfig
aesgcm, un RedisMemoryConfig les combinant en un RedisConversationMemory, la
promotion de MemoryConfig en union discriminée in_memory ou redis, les secrets
pepper et clé lus dans l'environnement et jamais dans le TOML.

## Key decisions

- **Les secrets viennent de l'environnement, jamais du TOML.** Le pepper du hasher
  vient de PIIGHOST_HASH_PEPPER, la clé du cipher de PIIGHOST_CIPHER_KEY encodée en
  base64. build() les lit, lève ConfigError si absents, comme le guard moderation
  en couverture A. Un secret dans un fichier de config serait committé par
  accident.
- **HasherConfig est une union, CipherConfig un alias.** Deux hashers existent,
  sha256 sans extra car HMAC est stdlib, et argon2 derrière l'extra argon2, donc
  HasherConfig est une union discriminée sur type. Un seul cipher existe, aesgcm,
  donc CipherConfig est un alias tant qu'un second n'arrive pas, comme LinkerConfig.
- **MemoryConfig devient une union discriminée.** Le champ memory de PipelineConfig
  accepte désormais in_memory ou redis, discriminé sur type. C'est le changement
  anticipé en C1, l'alias InMemoryConfig devient Annotated[InMemoryConfig |
  RedisMemoryConfig, Discriminator type].
- **Le client Redis est bâti depuis une URL.** RedisMemoryConfig porte une url,
  build() appelle Redis.from_url, qui parse sans se connecter, la connexion se fait
  au premier appel. Le namespace et le ttl sont des scalaires exposés.
- **build() couplé à sens unique, import différé derrière chaque extra.** Le port
  AnyHasher, AnyCipher, AnyConversationMemory est importé en tête pour l'annotation,
  la classe concrète dans build(), pour que redis, cryptography et argon2 restent
  optionnels à l'import de la config.

## Architecture

config/models/hasher.py (nouveau) :

- Sha256HasherConfig, type sha256, build() lisant PIIGHOST_HASH_PEPPER et renvoyant
  Sha256Hasher(pepper). Sans extra, HMAC-SHA256 est stdlib.
- Argon2HasherConfig, type argon2, time_cost int défaut 2, memory_cost int défaut
  19456, parallelism int défaut 1, hash_length int défaut 32, build() lisant le
  pepper et renvoyant Argon2Hasher(pepper, time_cost=..., memory_cost=...,
  parallelism=..., hash_length=...). Extra argon2.
- Un helper module lisant PIIGHOST_HASH_PEPPER, levant ConfigError si vide ou
  absent, partagé par les deux build().
- HasherConfig, Annotated[Sha256HasherConfig | Argon2HasherConfig, Discriminator
  type].

config/models/cipher.py (nouveau) :

- AesGcmCipherConfig, type aesgcm, build() lisant PIIGHOST_CIPHER_KEY, la décodant
  de base64, et renvoyant AesGcmCipher(key). Extra crypto. ConfigError si la clé est
  absente ou n'est pas du base64 valide ; une clé de mauvaise taille laisse
  AesGcmCipher lever son InvalidKeyLengthError, déjà un PIIGhostError clair.
- CipherConfig, alias d'AesGcmCipherConfig avec un docstring attaché disant qu'il
  devient une union quand un second cipher arrive.

config/models/memory.py (modifié) :

- RedisMemoryConfig, type redis, url str, namespace str défaut piighost, ttl int ou
  None défaut None, hasher HasherConfig, cipher CipherConfig. build() important en
  différé Redis depuis redis.asyncio et RedisConversationMemory, construisant le
  client par Redis.from_url(url) et renvoyant RedisConversationMemory(client,
  hasher construite, cipher construit, namespace, ttl). Extra redis.
- MemoryConfig passe de l'alias InMemoryConfig à Annotated[InMemoryConfig |
  RedisMemoryConfig, Discriminator type]. InMemoryConfig est inchangé.

settings.py n'a aucun changement, PipelineConfig.memory est déjà MemoryConfig ou
None, et MemoryConfig désigne maintenant l'union. load_thread_pipeline bâtit un
ThreadAnonymizationPipeline avec la mémoire choisie sans savoir laquelle.

## Errors

Aucune nouvelle exception. build() lève la ConfigError existante quand un secret,
pepper ou clé, manque ou que la clé n'est pas du base64. Une clé bien décodée mais
de mauvaise taille laisse remonter l'InvalidKeyLengthError du cipher, déjà sous
PIIGhostError. Un extra manquant, redis, crypto ou argon2, fait lever l'ImportError
de son module composant, nommant l'extra.

## Testing

Déterministe, les extras redis, cryptography, argon2 étant dans le dev, chaque
build() tourne hors ligne, Redis.from_url ne se connectant pas :

- Sha256HasherConfig.build() sous un PIIGHOST_HASH_PEPPER monkeypatché rend un
  Sha256Hasher ; Argon2HasherConfig.build() rend un Argon2Hasher et ses champs de
  coût sont stockés ;
- un pepper absent fait lever ConfigError aux deux hashers ;
- AesGcmCipherConfig.build() sous un PIIGHOST_CIPHER_KEY monkeypatché, base64 de 32
  octets, rend un AesGcmCipher ; une clé absente lève ConfigError ; un base64
  invalide lève ConfigError ;
- HasherConfig dispatche sha256 et argon2 sur type ;
- RedisMemoryConfig.build() sous les deux secrets rend un RedisConversationMemory,
  le client bâti par Redis.from_url sans réseau ;
- MemoryConfig dispatche in_memory vers InMemoryConfig et redis vers
  RedisMemoryConfig ;
- load_thread_pipeline sur un TOML déclarant une mémoire redis, avec hasher, cipher
  et url, et les deux secrets en environnement, bâtit un ThreadAnonymizationPipeline
  hors ligne ;
- le couplage à sens unique tient, le core n'importe pas config.

Packaging et régression PUBLIC_API : rien à ajouter. Les extras redis, crypto,
argon2 existent déjà, et les modèles de config vivent derrière l'extra config,
couverts par le walk. Aucune exception nouvelle.

## Out of scope

- Le client distant et le format JSON, sous-lot D.
- La rotation de clé, un KMS, un second cipher, un troisième hasher.
- Le paramètre separators et tout réglage fin du client Redis au-delà de l'URL, du
  namespace et du ttl.
- L'injection d'un client Redis vivant, d'un hasher ou d'un cipher déjà construit,
  la config n'accepte qu'une URL et des secrets d'environnement.
