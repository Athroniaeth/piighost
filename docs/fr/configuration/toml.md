# Référence de configuration

Module : `piighost.config`

Un fichier de configuration décrit un pipeline entier de façon déclarative. `piighost` le lit en TOML ou en JSON, choisi par le suffixe du fichier, le valide avec Pydantic, et construit le pipeline que le fichier décrit. Cette page documente chaque section et chaque `type` de composant.

```python
from piighost.config import load_config, load_pipeline, load_thread_pipeline
```

L'extra `config` est requis (`pip install piighost[config]`), qui tire `pydantic-settings`. Les clés inconnues sont rejetées, donc une faute de frappe échoue à la validation au lieu d'être ignorée.

---

## Points d'entrée

<div class="wide-table" markdown="1">

| Fonction | Renvoie | Construit | Mémoire |
|----------|---------|-----------|---------|
| `load_config(path)` | `PipelineConfig` | rien, valide seulement | quelconque |
| `load_pipeline(path)` | `AnonymizationPipeline` | un pipeline sans état | rejette une section `[memory]` |
| `load_thread_pipeline(path)` | `ThreadAnonymizationPipeline` | un pipeline de thread | requiert une section `[memory]` |

</div>

`load_config` analyse et valide un fichier en `PipelineConfig` sans construire de composant, donc aucun modèle ne charge. `load_pipeline` construit un `AnonymizationPipeline` sans état et lève `ConfigError` si le fichier déclare une section `[memory]`, car une mémoire décrit un pipeline de thread. `load_thread_pipeline` construit un `ThreadAnonymizationPipeline` et lève `ConfigError` si le fichier ne déclare aucune section `[memory]`.

```python
from piighost.config import load_pipeline, load_thread_pipeline

stateless = load_pipeline("pipeline.toml")       # no [memory]
thread = load_thread_pipeline("thread.toml")     # has [memory]
```

---

## Format de fichier

Le suffixe choisit le parseur. `.json` est lu en JSON, tout le reste en TOML. Les deux formats portent le même schéma. Une section est une table TOML ou un objet JSON.

```toml
[detector]
type = "regex"
patterns = { EMAIL = '[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}' }

[linker]
type = "exact"

[anonymizer.placeholder]
type = "redact"
```

```json
{
  "detector": { "type": "regex", "patterns": { "EMAIL": "[a-z0-9._%+-]+@[a-z0-9.-]+\\.[a-z]{2,}" } },
  "linker": { "type": "exact" },
  "anonymizer": { "placeholder": { "type": "redact" } }
}
```

---

## Surcharges par l'environnement

Les scalaires de premier niveau acceptent une surcharge par une variable d'environnement préfixée `PIIGHOST_`. Le seul scalaire de premier niveau est `name`, donc `PIIGHOST_NAME` surcharge la clé `name`. Les surcharges se superposent au fichier, donc une valeur d'environnement l'emporte sur la valeur du fichier.

Les secrets ne sont jamais lus depuis le fichier. Chacun est lu depuis sa propre variable d'environnement à la construction, et une variable manquante lève `ConfigError` depuis `build()`.

<div class="wide-table" markdown="1">

| Secret | Variable | Format | Utilisé par |
|--------|----------|--------|-------------|
| Poivre de hachage | `PIIGHOST_HASH_PEPPER` | toute chaîne non vide | `[memory.hasher]` |
| Clé de chiffrement | `PIIGHOST_CIPHER_KEY` | base64 de 16, 24 ou 32 octets | `[memory.cipher]` |
| Clé de modération | `MISTRAL_API_KEY` | clé d'API Mistral | `[guard]` type `moderation` |

</div>

---

## Sections

Les clés de premier niveau d'un `PipelineConfig`.

<div class="wide-table" markdown="1">

| Section | Requise | Signification |
|---------|---------|---------------|
| `name` | non | Un nom de pipeline optionnel, un scalaire de premier niveau surchargeable par `PIIGHOST_NAME` |
| `[detector]` | oui | L'étage de détection |
| `[linker]` | oui | Le linker d'entités |
| `[anonymizer]` | oui | L'étage de rendu, construit sur une factory de placeholders |
| `[overlap_resolver]` | non | Résout les détections qui se chevauchent |
| `[expander]` | non | Retrouve les occurrences manquées d'une valeur détectée |
| `[entity_resolver]` | non | Regroupe les entités qui désignent la même chose |
| `[guard]` | non | Revérifie la sortie pour une PII résiduelle |
| `[override]` | non | Force ou écarte des détections via une whitelist et une blacklist |
| `[observation_redactor]` | non | Une factory de placeholders caviardant les charges de trace |
| `[memory]` | non | La mémoire de conversation. Sa présence fait un pipeline de thread |

</div>

---

## `[detector]`

Discriminé sur `type`. Requis.

### `type = "regex"`

Applique un regex par label, tiré des `patterns` en ligne, des `catalogs` nommés, ou des deux. Les catalogues fusionnent d'abord, puis les patterns en ligne, donc un pattern en ligne l'emporte sur un pattern de catalogue au même label. Au moins un pattern en ligne ou un catalogue est requis. Chaque pattern est validé comme un regex compilable au chargement.

| Clé | Type | Défaut | Signification |
|-----|------|--------|---------------|
| `patterns` | `dict[str, str]` | `{}` | Correspondance label vers regex en ligne |
| `catalogs` | `list[str]` | `[]` | Catalogues prêts, parmi `generic`, `us`, `eu`, `fr` |

```toml
[detector]
type = "regex"
catalogs = ["generic", "fr"]
patterns = { EMPLOYEE_ID = 'EMP-[0-9]{4}' }
```

### `type = "composite"`

Exécute des détecteurs enfants ensemble et fusionne leurs détections.

| Clé | Type | Signification |
|-----|------|---------------|
| `detectors` | `list[detector]` | Les configs de détecteurs enfants, au moins un, sous `[[detector.detectors]]` |

```toml
[detector]
type = "composite"

[[detector.detectors]]
type = "regex"
catalogs = ["generic"]

[[detector.detectors]]
type = "exact"
values = { Patrick = "PERSON" }
```

### `type = "exact"`

Trouve les occurrences de valeurs littérales, chacune associée à un label.

| Clé | Type | Signification |
|-----|------|---------------|
| `values` | `dict[str, str]` | Correspondance valeur littérale vers label, au moins une |

```toml
[detector]
type = "exact"
values = { Patrick = "PERSON", Lyon = "LOCATION" }
```

### `type = "chunked"`

Enveloppe un détecteur avec un splitter qui découpe un texte long en tranches qui se chevauchent.

| Clé | Type | Défaut | Signification |
|-----|------|--------|---------------|
| `detector` | `detector` | | Le détecteur exécuté sur chaque tranche, sous `[detector.detector]` |
| `chunk_size` | `int` | `1000` | Taille maximale d'une tranche, supérieure à 0 |
| `chunk_overlap` | `int` | `100` | Chevauchement entre tranches, inférieur à `chunk_size` |

```toml
[detector]
type = "chunked"
chunk_size = 2000
chunk_overlap = 200

[detector.detector]
type = "spacy"
model = "en_core_web_sm"
```

### Détecteurs à modèle

Chacun nécessite un extra et un modèle. `labels` accepte une liste ou une map `{emitted: internal}`. `max_concurrency` plafonne les inférences concurrentes, ou `None` pour illimité.

<div class="wide-table" markdown="1">

| `type` | Extra | Clés |
|--------|-------|------|
| `gliner2` | `gliner2` | `model` (requis), `labels` (requis), `threshold` (défaut `0.5`), `max_concurrency` |
| `spacy` | `spacy` | `model` (requis), `labels`, `max_concurrency` |
| `transformers` | `transformers` | `model` (requis), `labels`, `threshold` (défaut `0.0`), `max_concurrency` |
| `llm` | `llm` | `model` (requis), `labels` (requis), `prompt`, `provider` |

</div>

```toml
[detector]
type = "gliner2"
model = "fastino/gliner2-multi-v1"
labels = ["PERSON", "LOCATION"]
threshold = 0.5
```

Le détecteur `llm` lit l'identifiant de son fournisseur depuis la variable d'environnement propre au fournisseur, jamais depuis le fichier.

---

## `[linker]`

Discriminé sur `type`. Requis.

| `type` | Signification |
|--------|---------------|
| `exact` | Regroupe les détections par valeur repliée en casse |

```toml
[linker]
type = "exact"
```

---

## `[anonymizer]`

L'étage de rendu. Requis. Il porte une table `[anonymizer.placeholder]` qui choisit la factory de placeholders, discriminée sur `type`.

<div class="wide-table" markdown="1">

| `type` | Token | Clés |
|--------|-------|------|
| `redact` | `<<REDACT>>`{ .placeholder } | |
| `label` | `<<PERSON>>`{ .placeholder } | |
| `label_counter` | `<<PERSON:1>>`{ .placeholder } | |
| `label_hash` | `<<PERSON:a1b2c3d4>>`{ .placeholder } | `hash_length` (défaut `8`) |
| `mask` | `P***`{ .placeholder } | `visible` (défaut `1`), `mask_char` (défaut `*`) |

</div>

```toml
[anonymizer.placeholder]
type = "label_counter"
```

Le middleware a besoin d'une factory délimitée, donc `redact`, `label`, `label_counter` ou `label_hash`. La factory `mask` produit `P***`{ .placeholder }, qui ne garde aucun délimiteur et n'a pas de reconnaisseur.

---

## `[overlap_resolver]`

Optionnel. Discriminé sur `type`.

| `type` | Signification |
|--------|---------------|
| `confidence` | Garde la détection la plus confiante quand deux se chevauchent |

```toml
[overlap_resolver]
type = "confidence"
```

---

## `[expander]`

Optionnel. Discriminé sur `type`.

| `type` | Clés | Signification |
|--------|------|---------------|
| `word_boundary` | `case_sensitive` (défaut `false`) | Retrouve les autres occurrences entières d'une valeur détectée |

```toml
[expander]
type = "word_boundary"
case_sensitive = false
```

---

## `[entity_resolver]`

Optionnel. Discriminé sur `type`.

| `type` | Clés | Signification |
|--------|------|---------------|
| `merge` | | Unit les entités qui partagent des détections |
| `separate` | | Garde chaque entité distincte |
| `fuzzy` | `threshold` (défaut `0.85`) | Regroupe les entités au-dessus d'une similarité de Jaro-Winkler |

```toml
[entity_resolver]
type = "fuzzy"
threshold = 0.85
```

---

## `[guard]`

Optionnel. Discriminé sur `type`. Revérifie la sortie dé-identifiée pour une PII résiduelle et la refuse quand une PII subsiste.

### `type = "detector"`

Réexécute un détecteur sur la sortie. Porte une config imbriquée `[guard.detector]`.

```toml
[guard]
type = "detector"

[guard.detector]
type = "regex"
patterns = { EMAIL = '[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}' }
```

### `type = "llm"`

Demande à un modèle de chat de trouver une PII résiduelle.

| Clé | Type | Signification |
|-----|------|---------------|
| `model` | `str` | L'identifiant du modèle de chat (requis) |
| `labels` | `list` ou `dict` | Les labels à chercher (requis) |
| `prompt` | `str` | Un prompt qui remplace celui par défaut, ou omis |
| `provider` | `str` | Le fournisseur, ou omis pour l'inférer du modèle |

### `type = "moderation"`

Note la sortie avec un modèle de modération Mistral. L'identifiant est lu depuis `MISTRAL_API_KEY` à la construction, et `build()` lève `ConfigError` quand il est absent.

| Clé | Type | Défaut | Signification |
|-----|------|--------|---------------|
| `model` | `str` | `mistral-moderation-latest` | Le modèle de modération |
| `threshold` | `float` | `0.5` | Le score de catégorie au-dessus duquel le texte est signalé |

---

## `[override]`

Optionnel. Force des détections via une whitelist et en écarte via une blacklist. Chaque liste est une config de détecteur, `[override.whitelist]` et `[override.blacklist]`, toutes deux optionnelles.

<div class="wide-table" markdown="1">

| Clé | Valeurs | Défaut | Signification |
|-----|---------|--------|---------------|
| `[override.whitelist]` | détecteur | | Un détecteur dont les hits sont forcés dans l'ensemble |
| `[override.blacklist]` | détecteur | | Un détecteur dont les hits invalident des détections |
| `blacklist_strategy` | `exact`, `value`, `overlap` | `exact` | Comment un hit de blacklist invalide : même span et label, même valeur repliée en casse, ou tout span en chevauchement |
| `whitelist_strategy` | `respect_provenance`, `force` | `respect_provenance` | Si un hit de whitelist laisse en clair une valeur introduite par l'assistant, ou la tokenise quand même |
| `conflict_strategy` | `whitelist_wins`, `blacklist_wins`, `raise` | `whitelist_wins` | Qui l'emporte quand les deux listes se contredisent. `raise` refuse la collision avec `ConflictingOverrideError` |

</div>

```toml
[override]
blacklist_strategy = "value"

[override.whitelist]
type = "regex"
patterns = { CODENAME = 'ACME-[A-Z]+' }

[override.blacklist]
type = "exact"
values = { "public@corp.com" = "EMAIL" }
```

---

## `[observation_redactor]`

Optionnel. Une config de factory de placeholders, mêmes valeurs de `type` que `[anonymizer.placeholder]`, caviardant les charges envoyées à un backend de traçage pour qu'une trace porte des tokens, pas des valeurs brutes.

```toml
[observation_redactor]
type = "label"
```

---

## `[memory]`

Optionnel. Sa présence fait du pipeline un `ThreadAnonymizationPipeline` qui garde un état par thread. Discriminé sur `type`.

### `type = "in_memory"`

Un stockage local au processus, perdu au redémarrage et non partagé entre workers.

```toml
[memory]
type = "in_memory"
```

### `type = "redis"`

Un stockage persistant et multi-worker. Chaque valeur stockée est indexée par un hacheur et chiffrée par un cipher.

| Clé | Type | Défaut | Signification |
|-----|------|--------|---------------|
| `url` | `str` | | L'URL de connexion Redis (requis) |
| `namespace` | `str` | `piighost` | Le préfixe de clé isolant les clés de cette librairie |
| `ttl` | `int` | `None` | Secondes de vie d'un message stocké, ou omis pour garder jusqu'à l'éviction |
| `[memory.hasher]` | hacheur | | Le hacheur qui indexe chaque message (requis) |
| `[memory.cipher]` | cipher | | Le cipher qui chiffre chaque valeur (requis) |

Le hacheur, `[memory.hasher]`, est discriminé sur `type`.

<div class="wide-table" markdown="1">

| `type` | Clés | Signification |
|--------|------|---------------|
| `sha256` | | HMAC-SHA256, un condensé rapide à clé |
| `argon2` | `time_cost` (défaut `2`), `memory_cost` (défaut `19456`), `parallelism` (défaut `1`), `hash_length` (défaut `32`) | Argon2id, un condensé lent et gourmand en mémoire |

</div>

Le cipher, `[memory.cipher]`, a un seul type.

| `type` | Signification |
|--------|---------------|
| `aesgcm` | Chiffrement authentifié AES-GCM des valeurs stockées |

Le hacheur lit son poivre depuis `PIIGHOST_HASH_PEPPER` et le cipher lit sa clé base64 depuis `PIIGHOST_CIPHER_KEY`, tous deux à la construction. Une valeur manquante ou mal formée lève `ConfigError`.

```toml
[memory]
type = "redis"
url = "redis://localhost:6379/0"
namespace = "piighost"
ttl = 3600

[memory.hasher]
type = "argon2"

[memory.cipher]
type = "aesgcm"
```

### `type = "sqlalchemy"`

Un stockage durable et multi-worker adossé à n'importe quelle base supportée par SQLAlchemy (SQLite, PostgreSQL, ...). Il lit l'URL de la base depuis une variable d'environnement plutôt que le fichier de config, pour que l'URL et son mot de passe restent hors du gestionnaire de versions. Un hacheur et un cipher optionnels protègent les valeurs stockées exactement comme pour Redis.

| Clé | Type | Défaut | Signification |
|-----|------|--------|---------------|
| `url_env` | `str` | `PIIGHOST_DATABASE_URL` | La variable d'environnement contenant l'URL async de la base |
| `table_name` | `str` | `piighost_conversation_messages` | La table stockant les messages par thread |
| `[memory.hasher]` | hacheur | | Optionnel. Le hacheur qui indexe chaque message |
| `[memory.cipher]` | cipher | | Optionnel. Le cipher qui chiffre chaque valeur |

L'URL doit utiliser un driver async, par exemple `postgresql+asyncpg://...` ou `sqlite+aiosqlite://...`. Une variable d'environnement manquante lève `ConfigError` à la construction. Appelez `await memory.create_schema()` une fois au démarrage pour créer la table.

```toml
[memory]
type = "sqlalchemy"
url_env = "PIIGHOST_DATABASE_URL"
table_name = "piighost_conversation_messages"

[memory.hasher]
type = "argon2"

[memory.cipher]
type = "aesgcm"
```

---

## Exemple complet

Un pipeline sans état qui tire un catalogue, ajoute un pattern en ligne, et active plusieurs étages optionnels.

```toml
name = "local-en"

[detector]
type = "regex"
catalogs = ["generic"]
patterns = { EMPLOYEE_ID = 'EMP-[0-9]{4}' }

[linker]
type = "exact"

[anonymizer.placeholder]
type = "label_counter"

[overlap_resolver]
type = "confidence"

[expander]
type = "word_boundary"

[entity_resolver]
type = "fuzzy"
threshold = 0.85

[override.whitelist]
type = "regex"
patterns = { CODENAME = 'ACME-[A-Z]+' }

[guard]
type = "detector"

[guard.detector]
type = "regex"
patterns = { EMAIL = '[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}' }

[observation_redactor]
type = "label"
```

Le même contenu en JSON, choisi par un suffixe `.json`, est équivalent. Une table devient un objet, une table en ligne devient un objet imbriqué, et un tableau de tables devient un tableau d'objets.

---

## Erreurs

<div class="wide-table" markdown="1">

| Erreur | Levée quand |
|--------|-------------|
| `ConfigFileError` | Le fichier est absent, illisible, ou du TOML ou JSON invalide |
| `ConfigValidationError` | Les données analysées échouent à la validation du schéma |
| `ConfigError` | Un secret manque à la construction, ou le mauvais point d'entrée est utilisé pour la mémoire déclarée |

</div>

`ConfigFileError` et `ConfigValidationError` sont des sous-classes de `ConfigError`, donc attraper `ConfigError` couvre les trois. Les classes vivent dans `piighost.exceptions`, donc un appelant peut les attraper sans l'extra `config`.

---

## Voir aussi

- [Interface en ligne de commande](../reference/cli.md) pour valider un fichier depuis le shell.
- [Référence Détecteurs](../reference/detectors.md) pour le détecteur que chaque `type` construit.
- [Référence de l'intégration LangChain](../reference/langchain.md) pour piloter un pipeline de thread dans un agent.
