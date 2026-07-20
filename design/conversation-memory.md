# Conception — ConversationMemory (repository)

Note de conception figée avant implémentation. À lire avec
`design/rewrite-blueprint.md` (§2 couches, §4 repository) et
`design/rewrite-progress.md`.

## Rôle

Repository qui persiste, par `thread_id`, les détections vues dans une
conversation (tours user **et** IA). Stocke des `Detection` uniquement ;
dériver les entités et leurs jetons est un service au-dessus du port, pas le
travail du store.

Une seule structure `(thread_id, message) -> détections` sert deux usages, tous
deux via `get_detections` selon qu'on passe un message ou non :

- **cache forward** (`get_detections(thread_id, message)`) : si l'user renvoie
  le même message, on retrouve ses détections sans relancer la détection (NER
  coûteux) ;
- **union** (`get_detections(thread_id)`) : aplatir toutes les détections du
  fil, en ordre first-seen, pour dériver entités + jetons.

## Port

```
remember(thread_id, message, detections)     -> None
get_detections(thread_id, message=None)      -> list[Detection] | None
forget(thread_id)                            -> Forgotten
```

- `get_detections` sans message (ou `None`) : union first-seen, toujours une
  liste. Avec un message : les détections cachées de ce message, où `None` =
  message jamais vu (relancer la détection) et `[]` = vu, zéro PII (hit propre,
  ne pas relancer). La distinction None/`[]` porte le cache. `None` sert de
  défaut « tout » sans Sentinel séparé, car un message est toujours un `str`.
- `Forgotten(messages: int, detections: int)` : preuve d'effacement (RGPD). Fil
  inconnu → `Forgotten(0, 0)`.
- Pas de template `Base*` : les backends diffèrent par tout leur mécanisme de
  stockage (dict, Redis, SQL), pas par un hook unique sur une entrée. Exception
  pairwise de la règle 20, comme le fuzzy resolver.

## Lookup par message avec clé hachée

L'user renvoie le message -> on le hache (hash déterministe + pepper) -> `GET`
direct par cette clé -> hit = détections, miss = None. Pas de scan, car le hash
est déterministe (même message -> même clé). C'est ce qui rend argon2 à sel
aléatoire inutilisable ici (il faudrait scanner + re-hacher chaque ligne).

## Clair / haché / chiffré

| Élément | État en BDD | Pourquoi |
|---|---|---|
| `thread_id` | clair (namespace de clé) | doit rester requêtable pour énumérer / effacer un fil |
| `message` | haché (HMAC-SHA256 + pepper) | clé de lookup, jamais stocké en clair, pas de PII lisible |
| détections (valeur) | chiffrées (AES-GCM, pyca cryptography) | la vraie PII ; un leak BDD -> ciphertext inutile |

## Backends

**InMemoryConversationMemory** (dev, tests, mono-process). Dict en clair
`dict[thread_id, dict[message, list[Detection]]]`. Aucun besoin de crypto. Rien
n'est conservé au redémarrage, rien n'est partagé entre process.

**RedisConversationMemory** (multi-worker, plus tard). Layout :

```
{ns}:{thread_id}:msg:{hash(message)}  ->  encrypt(serde(detections))   # 1 par message
{ns}:{thread_id}:index                ->  [hash1, hash2, ...]          # ordre first-seen
```

Le `hash(message)` seul ne garantit pas l'ordre (SCAN non ordonné) -> un index
ordonné par thread (liste Redis) tient l'ordre d'insertion. C'est le per-thread
key index de v1 (aiocache/redis sans scan de préfixe portable et ordonné).

Flux :

- `get_detections(thread_id, message)` : `key = {ns}:{thread_id}:msg:` +
  `hasher.hash(message)` ; `GET` ; hit -> `serde.loads(cipher.decrypt(value))` ;
  miss -> `None`.
- `get_detections(thread_id)` : lire l'index (ordre) ; `GET` + déchiffrer chaque
  entrée ; aplatir dans l'ordre.
- `forget` : lire l'index -> toutes les clés ; `DEL` entrées + index ; compter
  -> `Forgotten`.

## Injection crypto

Ctor du backend persistant, tout injecté, tout optionnel derrière extra + garde
`find_spec` :

```
RedisConversationMemory(client, *, serde, hasher, cipher, namespace, ttl)
```

- `hasher` : message -> hash (HmacSha256 défaut / Argon2 optionnel), ports
  interchangeables, pepper global via env.
- `cipher` : bytes -> bytes (AES-GCM, pyca cryptography, clé via env).
- `serde` : `list[Detection]` <-> bytes (JSON / msgpack).

L'in-memory ne dépend d'aucun des trois.

## Points ouverts

- Compte des détections au `forget` : décrypter-et-compter, ou compteur stocké ?
- Nonce AES-GCM : aléatoire par valeur, préfixé au ciphertext.
- Isolation renforcée : lier `thread_id` comme associated data de l'HMAC / AEAD
  (empêche de rejouer une valeur d'un fil dans un autre). Optionnel.
- TTL : `cache_ttl` par entrée ; le `forget` reste explicite pour le RGPD.
- Dédup : le store reste bête ; la dédup en entités se fait à la dérivation
  (linker), pas ici.
