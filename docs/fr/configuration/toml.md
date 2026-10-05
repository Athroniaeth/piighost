# Référence de configuration

Module : `piighost.config`

Un fichier de configuration décrit un pipeline entier de façon déclarative. `piighost` le lit en TOML ou en JSON, selon le suffixe du fichier. Il le valide ensuite avec Pydantic, puis construit le pipeline que le fichier décrit. Cette page documente chaque section et chaque `type` de composant.

```python
from piighost.config import load_config, load_pipeline, load_thread_pipeline
```

L'extra `config` est requis (`pip install "piighost[config]"`). Il tire `pydantic-settings`. Les clés inconnues sont rejetées, donc une faute de frappe échoue à la validation au lieu d'être ignorée. Un `type` de composant peut demander son propre extra, nommé dans la colonne Extra du tableau qui le documente.

---

## Points d'entrée

<div class="wide-table" markdown="1">

| Fonction | Renvoie | Construit | Mémoire |
|----------|---------|-----------|---------|
| `load_config(path)` | `PipelineConfig` | rien, valide seulement | quelconque |
| `load_pipeline(path)` | `AnonymizationPipeline` | un pipeline sans état | rejette une section `[memory]` |
| `load_thread_pipeline(path)` | `ThreadAnonymizationPipeline` | un pipeline de conversation | requiert une section `[memory]` |

</div>

`load_config` analyse et valide un fichier en `PipelineConfig` sans construire de composant, donc aucun modèle ne charge. `load_pipeline` construit un `AnonymizationPipeline` sans état et lève `ConfigError` si le fichier déclare une section `[memory]`, car une mémoire décrit un pipeline de conversation. `load_thread_pipeline` construit un `ThreadAnonymizationPipeline` et lève `ConfigError` si le fichier ne déclare aucune section `[memory]`.

```python
--8<-- "snippets/toml_loaders.py"
```

---

## Format de fichier

Le suffixe choisit le parseur. Un suffixe `.json` est lu en JSON, quelle que soit sa casse. Tout autre suffixe est lu en TOML. Les deux formats portent le même schéma. Une section est une table TOML ou un objet JSON.

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

Chaque clé de premier niveau accepte une surcharge par une variable d'environnement préfixée `PIIGHOST_`, qu'elle porte un scalaire ou une section entière. `PIIGHOST_NAME` surcharge le scalaire `name`. `PIIGHOST_DETECTOR` surcharge la section `[detector]` avec un objet JSON. Si ce n'est pas du JSON valide, la variable est rejetée comme erreur de validation. Les surcharges se superposent au fichier clé par clé. Une valeur d'environnement l'emporte sur celle du fichier, et les clés qu'elle omet gardent la valeur du fichier.

```bash
export PIIGHOST_NAME="local-en"
export PIIGHOST_DETECTOR='{"type": "exact", "values": {"Patrick": "PERSON"}}'
```

Aucun délimiteur d'imbrication n'est configuré. Une variable comme `PIIGHOST_DETECTOR__TYPE` ne nomme donc aucun champ. Elle est ignorée sans erreur au lieu d'atteindre la clé `type`. Une section se surcharge uniquement par son objet JSON.

Les secrets ne sont jamais lus depuis le fichier. Chacun est lu depuis sa propre variable d'environnement à la construction, et une variable manquante lève `ConfigError` depuis `build()`.

<div class="wide-table" markdown="1">

| Secret | Variable | Format | Utilisé par |
|--------|----------|--------|-------------|
| Poivre de hachage | `PIIGHOST_HASH_PEPPER` | toute chaîne non vide | `[memory.hasher]` |
| Clé de chiffrement | `PIIGHOST_CIPHER_KEY` | base64 de 16, 24 ou 32 octets | `[memory.cipher]` |
| Clé de modération | `MISTRAL_API_KEY` | clé d'API Mistral | `[guard]` type `moderation` |
| URL de base de données | la valeur de `url_env`, `PIIGHOST_DATABASE_URL` par défaut | une URL SQLAlchemy async | `[memory]` type `sqlalchemy` |

</div>

---

## Sections

Les clés de premier niveau d'un `PipelineConfig`.

<div class="wide-table" markdown="1">

| Section | Requise | Signification |
|---------|---------|---------------|
| `name` | non | Un nom de pipeline optionnel, un scalaire de premier niveau surchargeable par `PIIGHOST_NAME` |
| `token_memo_ttl` | non | Le nombre de secondes pendant lesquelles la carte de jetons mémoïsée d'une conversation est gardée. Un scalaire de premier niveau, qui exige un `[memory]` |
| `[detector]` | oui | L'étage de détection |
| `[linker]` | non | Le linker d'entités, par défaut `ExactEntityLinker` |
| `[anonymizer]` | non | L'étage de rendu, par défaut un `Anonymizer` avec une factory label-counter |
| `[overlap_resolver]` | non | Résout les détections qui se chevauchent, par défaut `ConfidenceOverlapResolver` |
| `[expander]` | non | Retrouve les occurrences manquées d'une valeur détectée |
| `[entity_resolver]` | non | Regroupe les entités qui désignent la même chose |
| `[guard]` | non | Revérifie la sortie pour des données confidentielles résiduelles |
| `[override]` | non | Force ou écarte des détections via une liste à masquer et une liste à laisser en clair |
| `[observation_redactor]` | non | Une factory de placeholders caviardant les charges de trace |
| `[memory]` | non | La mémoire de conversation. Sa présence fait un pipeline de conversation |

</div>

---

## `[detector]`

Discriminé sur `type`. Requis.

### `type = "regex"`

Applique un regex par label, tiré des `patterns` en ligne, des groupes du catalogue listés dans `catalogs`, ou des deux. Les groupes fusionnent d'abord, puis les patterns en ligne. Un pattern en ligne l'emporte donc sur un pattern de catalogue de même label. Au moins un pattern en ligne ou un catalogue est requis. Au chargement, chaque pattern est validé comme un regex compilable. Il est ensuite compilé sous `re.ASCII`, donc `\d` correspond à `0-9` et `\w` s'arrête au premier caractère non ASCII. Un motif écrit avec `\w` reconnaît donc `prénom@corp.com`{ .pii } à partir de `nom`. Pour inclure toutes les lettres, limitez le drapeau Unicode à la classe, `(?u:\w)`, ou nommez une plage. Le motif `EMAIL` de `catalog:piighost/generic` nomme ainsi la plage latine `À-ɏ`. Voir [Limites](../limitations.md) pour ce que chaque choix manque.

| Clé | Type | Défaut | Signification |
|-----|------|--------|---------------|
| `patterns` | `dict[str, str]` | `{}` | Correspondance label vers regex en ligne |
| `catalogs` | `list[str]` | `[]` | Références du catalogue, `catalog:namespace/name` avec un `:selector` optionnel. Une référence `hub:` de la 1.x est toujours acceptée. Toute autre entrée échoue à la validation |

```toml
[detector]
type = "regex"
catalogs = ["catalog:piighost/generic", "catalog:piighost/fr"]
patterns = { EMPLOYEE_ID = 'EMP-[0-9]{4}' }
```

Un groupe est récupéré depuis le catalogue à la construction de la config, pas à sa lecture. Une référence épinglée sur un commit est récupérée une fois, puis relue depuis le cache sur disque. `PIIGHOST_CATALOG_URL` désigne un registre privé, et `PIIGHOST_HUB_URL` de la 1.x est toujours lue quand elle n'est pas posée. Les noms `generic`, `us`, `eu` et `fr` sont refusés. Voir [Groupes du catalogue](../reference/detectors.md#groupes-du-catalogue) pour les groupes qui les remplacent.

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
catalogs = ["catalog:piighost/generic"]

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

Chacun nécessite son propre extra, et tous sauf `presidio` nécessitent un modèle. `labels` accepte une liste ou une map `{emitted: internal}`. `max_concurrency` plafonne les inférences concurrentes. `None` les laisse illimitées.

<div class="wide-table" markdown="1">

| `type` | Extra | Clés |
|--------|-------|------|
| `gliner2` | `gliner2` | `model` (requis), `labels` (requis), `threshold` (défaut `0.5`), `max_concurrency`, `max_chars` |
| `spacy` | `spacy` | `model` (requis), `labels`, `max_concurrency` |
| `transformers` | `transformers` | `model` (requis), `labels`, `threshold` (défaut `0.0`), `aggregation_strategy` (défaut `simple`), `max_concurrency`, `max_chars` |
| `presidio` | `presidio` | `labels`, `language` (défaut `en`), `threshold` (défaut `0.0`) |
| `llm` | `llm` | `model` (requis), `labels` (requis), `prompt`, `provider` |

</div>

```toml
[detector]
type = "gliner2"
model = "fastino/gliner2-multi-v1"
labels = ["PERSON", "LOCATION"]
threshold = 0.5
max_chars = 2000
```

Les détecteurs `gliner2` et `transformers` acceptent `max_chars`, le plus long texte qu'une inférence voit. Un texte plus long est découpé en morceaux qui se chevauchent. Chaque morceau est analysé séparément, puis les spans sont replacés dans le texte d'origine. Sans cette clé, le texte entier part au modèle en une fois. Un modèle à fenêtre courte tronque alors ce texte, et un long document peut épuiser la mémoire.

Le détecteur `transformers` passe `aggregation_strategy` à sa pipeline de classification de tokens, qui regroupe les sous-tokens en entités entières.

Le détecteur `presidio` ne prend aucune clé `model`, car le chemin par configuration construit l'`AnalyzerEngine` anglais par défaut de Presidio avec ses reconnaisseurs par défaut. Une autre langue, un reconnaisseur sur mesure ou un moteur NLP sur mesure passent par le chemin programmatique, en construisant le moteur et en le passant à `PresidioDetector`.

Le détecteur `llm` lit l'identifiant de son fournisseur depuis la variable d'environnement propre au fournisseur, jamais depuis le fichier.

---

## `[linker]`

Optionnel. Par défaut `ExactEntityLinker`. Un seul linker existe, donc `type` le nomme sans discriminer une union.

| `type` | Signification |
|--------|---------------|
| `exact` | Regroupe les détections par valeur, les mêmes mots quelles que soient leurs espaces et leur casse |

```toml
[linker]
type = "exact"
```

---

## `[anonymizer]`

Optionnel. Par défaut un `Anonymizer` avec une factory label-counter. Quand il est présent, il porte une table `[anonymizer.placeholder]` qui choisit la factory de placeholders, discriminée sur `type`.

<div class="wide-table" markdown="1">

| `type` | Jeton | Clés |
|--------|-------|------|
| `redact` | `<<REDACT>>`{ .placeholder } | |
| `label` | `<<PERSON>>`{ .placeholder } | |
| `label_counter` | `<<PERSON:1>>`{ .placeholder } | |
| `label_hash` | `<<PERSON:a1b2c3d4>>`{ .placeholder } | `hash_length` (défaut `8`, au moins 1) |
| `mask` | `P***`{ .placeholder } | `visible` (défaut `1`, 0 ou plus), `mask_char` (défaut `*`, exactement un caractère) |

</div>

```toml
[anonymizer.placeholder]
type = "label_counter"
```

Le middleware a besoin d'une factory délimitée, c'est-à-dire `redact`, `label`, `label_counter` ou `label_hash`. La factory `mask` produit `P***`{ .placeholder }, qui ne garde aucun délimiteur et n'a pas de reconnaisseur.

---

## `[overlap_resolver]`

Optionnel dans le fichier, mais l'étage tourne dans tous les cas. Omettre la section construit un `ConfidenceOverlapResolver`. Il n'existe aucun moyen supporté de désactiver l'étage, car l'étage de rendu suppose des spans disjoints.

| `type` | Signification |
|--------|---------------|
| `confidence` | Garde la détection la plus confiante quand deux se chevauchent |
| `merge` | Garde l'union des détections qui se chevauchent, avec le label de la plus confiante. À confiance égale, c'est le label de la plus large |

```toml
[overlap_resolver]
type = "merge"
```

`merge` cache chaque caractère qu'un détecteur a relevé. Avec `confidence`, une regex à confiance 1.0 qui a trouvé `Wirth`{ .pii } l'emporte sur un modèle qui a trouvé `Loni M. Wirth`{ .pii }. `Loni M.`{ .pii } part alors en clair. Choisissez `merge` quand une fuite coûte plus qu'un mot voisin masqué, comme dans un document traité par des règles et un modèle ensemble.

---

## `[expander]`

Optionnel, et désactivé quand il est omis. Un seul expander existe, donc `type` le nomme sans discriminer une union.

| `type` | Clés | Signification |
|--------|------|---------------|
| `word_boundary` | `case_sensitive` (défaut `false`) | Retrouve les autres occurrences entières d'une valeur détectée, quelles que soient les espaces entre ses mots |

```toml
[expander]
type = "word_boundary"
case_sensitive = false
```

---

## `[entity_resolver]`

Optionnel. Discriminé sur `type`.

| `type` | Extra | Clés | Signification |
|--------|-------|------|---------------|
| `merge` | | | Unit les entités qui partagent des détections |
| `separate` | | | Garde chaque entité distincte |
| `fuzzy` | `fuzzy` | `threshold` (défaut `0.85`) | Regroupe les entités au-dessus d'une similarité de Jaro-Winkler |

```toml
[entity_resolver]
type = "fuzzy"
threshold = 0.85
```

---

## `[guard]`

Optionnel. Discriminé sur `type`. Revérifie la sortie dé-identifiée pour des données confidentielles résiduelles et la refuse quand il en subsiste.

| `type` | Extra | Revérifie avec |
|--------|-------|----------------|
| `detector` | | Un détecteur réexécuté sur la sortie |
| `llm` | `llm` | Un modèle de chat à qui l'on demande la PII résiduelle |
| `moderation` | `mistral` | Un modèle de modération Mistral qui note la sortie |
| `gliner2` | `gliner2` | Un modèle garde-fou GLiNER2 local qui classe la sortie |

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

### `type = "gliner2"`

Classe la sortie avec un modèle garde-fou GLiNER2 qui tourne dans le processus, sans aucun identifiant. Le checkpoint est téléchargé à la première construction, puis lu depuis le cache Hugging Face.

| Clé | Type | Défaut | Signification |
|-----|------|--------|---------------|
| `model` | `str` | `fastino/GLiNER2-Guardrails-PII-Multi` | Le checkpoint GLiNER2 avec lequel le garde-fou classe |
| `task` | `str` | `response_safety` | La tâche de classification lue dans la réponse du modèle |
| `labels` | `list` | `["safe", "unsafe"]` | Les réponses entre lesquelles la tâche choisit, deux au moins. La réponse refusée vient en dernier |
| `threshold` | `float` | `0.5` | La confiance à partir de laquelle une réponse refusée signale la sortie |

```toml
[guard]
type = "gliner2"
threshold = 0.5
```

---

## `[override]`

Optionnel. Force des détections via une liste à masquer, dont les valeurs sont toujours masquées, et en écarte via une liste à laisser en clair, dont les valeurs restent toujours en clair. Chaque liste est une config de détecteur, `[override.deny_list]` et `[override.allow_list]`, toutes deux optionnelles. Les clés de la 1.x, `whitelist`, `blacklist` et leurs stratégies, sont refusées au chargement avec la clé qui les remplace, voir [Passer à la 2.0](../community/upgrading.md#les-listes-de-loverride-sont-renommees).

<div class="wide-table" markdown="1">

| Clé | Valeurs | Défaut | Signification |
|-----|---------|--------|---------------|
| `[override.deny_list]` | détecteur | | Un détecteur dont les hits sont toujours masqués, forcés dans l'ensemble |
| `[override.allow_list]` | détecteur | | Un détecteur dont les hits restent toujours en clair, en invalidant les détections qu'ils recouvrent |
| `allow_list_strategy` | `exact`, `value`, `overlap` | `value` | Comment un hit de la liste à laisser en clair invalide une détection. `value` exige la même valeur, quelles que soient ses espaces et sa casse. `exact` exige le même span et le même label. `overlap` invalide tout span en chevauchement |
| `deny_list_strategy` | `respect_provenance`, `force` | `respect_provenance` | Si un hit de la liste à masquer laisse en clair une valeur introduite par l'assistant, ou la dé-identifie quand même |
| `conflict_strategy` | `deny_list_wins`, `allow_list_wins`, `raise` | `deny_list_wins` | Qui l'emporte quand les deux listes se contredisent. `raise` refuse la collision avec `ConflictingOverrideError` |

</div>

```toml
[override]
allow_list_strategy = "value"

[override.deny_list]
type = "regex"
patterns = { CODENAME = 'ACME-[A-Z]+' }

[override.allow_list]
type = "exact"
values = { "public@corp.com" = "EMAIL" }
```

---

## `[observation_redactor]`

Optionnel. Une config de factory de placeholders, avec les mêmes valeurs de `type` que `[anonymizer.placeholder]`. Elle caviarde les charges envoyées à un backend de traçage, pour qu'une trace porte des jetons et pas des valeurs brutes.

```toml
[observation_redactor]
type = "label"
```

Sans cette section, le texte en clair et les valeurs détectées sont tracés. Un traceur actif émet alors un `PIIGhostSecurityWarning`. Le drapeau `trace_clear_text` du pipeline fait taire cet avertissement, mais il n'a aucune clé dans un fichier de configuration. Un pipeline construit depuis un fichier ne peut donc pas assumer le traçage en clair. Passer `trace_clear_text=True` au pipeline est le chemin programmatique.

---

## `[memory]`

Optionnel. Sa présence fait du pipeline un `ThreadAnonymizationPipeline` qui garde un état par conversation. Discriminé sur `type`.

Le scalaire `token_memo_ttl` va avec cette section, mais il se pose au premier niveau, parce qu'il borne la carte de jetons mémoïsée du pipeline et non le store. Le poser sans `[memory]` lève une erreur, parce qu'un pipeline sans état ne mémoïse rien. [Déploiement multi-instance](../multi-instance.md) explique pourquoi il compte sur un déploiement multi-worker.

| `type` | Extra | Stockage |
|--------|-------|----------|
| `in_memory` | | Local au processus, perdu au redémarrage |
| `redis` | `redis` | Persistant, partagé entre workers |
| `sqlalchemy` | `sqlalchemy` | Durable, dans une base SQL |

### `type = "in_memory"`

Un stockage local au processus, perdu au redémarrage et non partagé entre workers.

| Clé | Type | Défaut | Signification |
|-----|------|--------|---------------|
| `max_threads` | `int` | `10000` | Plafond de conversations gardées, éviction LRU au-delà (au moins 1) |
| `ttl` | `float` | `86400` | Durée d'inactivité, en secondes, après laquelle une conversation expire (supérieur à 0). Elle n'est retirée qu'au prochain accès |

```toml
[memory]
type = "in_memory"
```

### `type = "redis"`

Un stockage persistant et multi-worker. En option, il indexe chaque message stocké avec un hacheur et chiffre chaque valeur stockée avec un cipher.

| Clé | Type | Défaut | Signification |
|-----|------|--------|---------------|
| `url` | `str` | | L'URL de connexion Redis (requis) |
| `namespace` | `str` | `piighost` | Le préfixe de clé isolant les clés de cette librairie |
| `ttl` | `int` | `None` | Secondes de vie d'un message stocké, ou omis pour garder jusqu'à l'éviction |
| `[memory.hasher]` | hacheur | | Optionnel (les deux ou aucun). Le hacheur qui indexe chaque message |
| `[memory.cipher]` | cipher | | Optionnel (les deux ou aucun). Le cipher qui chiffre chaque valeur |

Configurez les deux, `[memory.hasher]` et `[memory.cipher]`, ou aucun. Sans aucun, le backend stocke la correspondance en clair et émet un avertissement. Avec un seul, `build()` lève `ConfigError`.

Le hacheur, `[memory.hasher]`, est discriminé sur `type`.

<div class="wide-table" markdown="1">

| `type` | Extra | Clés | Signification |
|--------|-------|------|---------------|
| `sha256` | | | HMAC-SHA256, un condensé rapide à clé |
| `argon2` | `argon2` | `time_cost` (défaut `2`), `memory_cost` (défaut `19456`), `parallelism` (défaut `1`), `hash_length` (défaut `32`) | Argon2id, un condensé lent et gourmand en mémoire |

</div>

Le cipher, `[memory.cipher]`, a un seul type.

| `type` | Extra | Signification |
|--------|-------|---------------|
| `aesgcm` | `crypto` | Chiffrement authentifié AES-GCM des valeurs stockées |

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
| `table_name` | `str` | `piighost_conversation_messages` | La table stockant les messages par conversation |
| `[memory.hasher]` | hacheur | | Optionnel (les deux ou aucun). Le hacheur qui indexe chaque message |
| `[memory.cipher]` | cipher | | Optionnel (les deux ou aucun). Le cipher qui chiffre chaque valeur |

Configurez les deux, `[memory.hasher]` et `[memory.cipher]`, ou aucun, exactement comme pour Redis. Sans aucun, le backend stocke la correspondance en clair et émet un avertissement. Avec un seul, `build()` lève `ConfigError`.

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

Les clés de `examples/config/pipeline.toml`, un pipeline sans état qui tire un groupe du catalogue, ajoute un pattern en ligne, et active plusieurs étages optionnels. Le fichier lui-même porte les mêmes clés avec un commentaire sur chaque étage.

```toml
[detector]
type = "regex"
catalogs = ["catalog:piighost/generic"]
patterns = { EMPLOYEE_ID = 'EMP-[0-9]{4}' }

[overlap_resolver]
type = "confidence"

[expander]
type = "word_boundary"

[entity_resolver]
type = "fuzzy"
threshold = 0.85

[linker]
type = "exact"

[anonymizer.placeholder]
type = "label_counter"

[override.deny_list]
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

- `examples/config/` dans le dépôt pour six fichiers exécutables, `detector_only.toml`, `minimal.toml`, `minimal.json`, `pipeline.toml`, `thread_redis.toml` et `thread_sqlalchemy.toml`, tous les six chargés par `examples/config/run.py`.
- [Interface en ligne de commande](../reference/cli.md) pour valider un fichier depuis le shell.
- [Référence Détecteurs](../reference/detectors.md) pour le détecteur que chaque `type` construit.
- [Référence de l'intégration LangChain](../reference/langchain.md) pour piloter un pipeline de conversation dans un agent.
- [Configurer un pipeline par fichier, catalogue et ligne de commande](../../../openwiki/fr/operations/configuration-and-catalog.md) pour les règles de configuration, de `BR-CFG-01` à `BR-CFG-09`, et leur emplacement dans le code.
