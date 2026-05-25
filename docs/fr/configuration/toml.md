# Configuration TOML du pipeline

`piighost` accepte un fichier TOML déclaratif qui décrit entièrement un
`ThreadAnonymizationPipeline`. Ce fichier est utilisé par :

- Le serveur `piighost-api` (`piighost-api serve --config <file>`).
- Les commandes CLI `piighost validate` et `piighost schema`.
- Toute application qui importe `piighost.config.load_pipeline`.

Aucun code Python n'est exécuté au chargement. Le format est entièrement
validé par Pydantic v2 ; les clés inconnues lèvent une erreur au lieu d'être
silencieusement ignorées.

## Exemple minimal

```toml
[[detectors]]
type = "regex"
patterns = { EMAIL = "[a-zA-Z0-9._%+\\-]+@[a-zA-Z0-9.\\-]+\\.[a-zA-Z]{2,}" }
```

Ce fragment produit un pipeline avec un détecteur regex, les résolveurs de
spans et d'entités par défaut, et la factory de placeholders `label_counter`
(qui génère des marqueurs du type `<<EMAIL_1>>`).

## Exemple complet

```toml
[pipeline]
name = "pii-en-multi"
description = "GLiNER2 + regex coverage for English text"
schema_version = 1

[[detectors]]
name = "common"
type = "regex"
patterns = { EMAIL = "[a-z]+@[a-z]+\\.[a-z]+", IP_V4 = "\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b" }

[[detectors]]
name = "gliner2"
type = "gliner2"
model = "fastino/gliner2-multi-v1"
threshold = 0.5
labels = ["person", "city", "email address"]

[span_resolver]
type = "confidence"

[entity_linker]
type = "exact"

[entity_resolver]
type = "merge"

[anonymizer.placeholder_factory]
type = "label_counter"
```

## Référence

### `[pipeline]` (optionnel)

| Clé              | Type    | Défaut | Signification                                |
| ---------------- | ------- | ------ | -------------------------------------------- |
| `name`           | string  | `null` | Exposé par `/v1/labels`.                     |
| `description`    | string  | `null` | Documentation libre, non utilisée par le code. |
| `schema_version` | integer | `1`    | Seule valeur valide pour l'instant.          |

### `[[detectors]]` (obligatoire, au moins un)

Chaque entrée déclare un détecteur. Plusieurs entrées forment implicitement
un `CompositeDetector`, dans l'ordre de déclaration.

Clés communes :

| Clé    | Type    | Obligatoire | Signification                                    |
| ------ | ------- | ----------- | ------------------------------------------------ |
| `type` | string  | oui         | Discriminant (`regex`, `gliner2`, ...).           |
| `name` | string  | non         | Utilisé pour le regroupement dans `/v1/labels`.  |

Par `type` :

**`regex`**

| Clé        | Type             | Obligatoire | Signification                           |
| ---------- | ---------------- | ----------- | --------------------------------------- |
| `patterns` | table[str, str]  | oui         | Nom du label vers le motif regex.       |

**`gliner2`** (nécessite `piighost[gliner2]`)

| Clé         | Type     | Obligatoire | Signification                                    |
| ----------- | -------- | ----------- | ------------------------------------------------ |
| `model`     | string   | oui         | Identifiant du modèle HF, ex. `fastino/gliner2-multi-v1`. |
| `labels`    | list[str]| oui         | Types d'entités à rechercher.                    |
| `threshold` | float    | non         | Seuil de confiance, défaut `0.5`.                |
| `flat_ner`  | bool     | non         | Défaut `true`.                                   |

**`spacy`** (nécessite `piighost[spacy]`)

| Clé      | Type     | Obligatoire | Signification                             |
| -------- | -------- | ----------- | ----------------------------------------- |
| `model`  | string   | oui         | Nom du modèle spaCy.                      |
| `labels` | list[str]| oui         | Types d'entités spaCy à conserver.        |

**`transformers`** (nécessite `piighost[transformers]`)

| Clé         | Type   | Obligatoire | Signification                                    |
| ----------- | ------ | ----------- | ------------------------------------------------ |
| `model`     | string | oui         | Identifiant du modèle HF.                        |
| `threshold` | float  | non         | Seuil de confiance, défaut `0.5`.                |

**`llm`** (nécessite `piighost[llm]`, secrets dans l'environnement)

| Clé        | Type     | Obligatoire | Signification                             |
| ---------- | -------- | ----------- | ----------------------------------------- |
| `provider` | string   | oui         | Ex. `openai`, `anthropic`.                |
| `model`    | string   | oui         | Identifiant de modèle propre au fournisseur. |
| `labels`   | list[str]| oui         | Labels à extraire.                        |

Les clés d'API ne sont jamais stockées dans le TOML. Elles sont lues depuis
les variables d'environnement par le client du fournisseur.

**`chunked`** (enveloppe un autre détecteur)

| Clé          | Type           | Obligatoire | Signification                              |
| ------------ | -------------- | ----------- | ------------------------------------------ |
| `chunk_size` | integer (>= 1) | oui         | Fenêtre de caractères par tranche.          |
| `overlap`    | integer (>= 0) | non         | Chevauchement entre les tranches, défaut 0. |
| `inner`      | detector cfg   | oui         | Le détecteur à exécuter sur chaque tranche. |

### `[span_resolver]` (optionnel, défaut `confidence`)

| `type`        | Comportement                                                          |
| ------------- | --------------------------------------------------------------------- |
| `confidence`  | Conserve la détection avec la confiance la plus haute en cas de chevauchement. |
| `disabled`    | Aucune résolution de conflit.                                          |

### `[entity_linker]` (optionnel, défaut `exact`)

| `type`     | Comportement                                                      |
| ---------- | ----------------------------------------------------------------- |
| `exact`    | Une regex à frontière de mot relie les mentions répétées.         |
| `disabled` | Aucun lien entre les mentions.                                    |

### `[entity_resolver]` (optionnel, défaut `merge`)

| `type`     | Comportement                     | Clé supplémentaire |
| ---------- | -------------------------------- | ------------------ |
| `merge`    | Fusion par union-find.           |                    |
| `fuzzy`    | Fusion par Jaro-Winkler.         | `threshold` (float, 0.0..1.0, défaut `0.85`). |
| `disabled` | Aucune fusion d'entités.         |                    |

### `[anonymizer]` (optionnel, défaut `default`)

```toml
[anonymizer]
type = "default"

[anonymizer.placeholder_factory]
type = "label_counter"     # see below
```

### `[anonymizer.placeholder_factory]` (optionnel, défaut `label_counter`)

| `type`            | Format du marqueur                      | Clés supplémentaires                       |
| ----------------- | --------------------------------------- | ------------------------------------------ |
| `label_counter`   | `<<PERSON_1>>`                          |                                            |
| `label_hash`      | `<<PERSON_a1b2c3>>`                     | `hash_length` (4..64, défaut 8)            |
| `label`           | `<<PERSON>>` (sans désambiguïsation)    |                                            |
| `mask`            | `*****`                                 | `mask_char` (1 caractère, défaut `*`)      |
| `redact_counter`  | `<<REDACTED_1>>`                        |                                            |
| `redact_hash`     | `<<REDACTED_a1b2c3>>`                   | `hash_length`                              |
| `redact`          | `<<REDACTED>>`                          |                                            |
| `faker_counter`   | Valeur synthétique réaliste, indexée    | `locale` (défaut `en_US`)                  |
| `faker_hash`      | Valeur synthétique réaliste, hashée     | `locale`, `hash_length`                    |
| `faker`           | Valeur synthétique réaliste             | `locale`                                   |

Les factories basées sur Faker nécessitent `piighost[faker]`.

## Commandes CLI

```
$ piighost validate ./pipeline.toml
OK: pipeline.toml

$ piighost schema > schema.json
```

`schema.json` est le schéma JSON canonique décrivant la structure
ci-dessus, utilisable pour l'autocomplétion dans les éditeurs ou dans
toute future interface web.
