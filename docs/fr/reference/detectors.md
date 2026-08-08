---
icon: lucide/list
tags:
  - Détecteur
  - Regex
---

# Référence Détecteurs

Module : `piighost.components.detector`

Un détecteur est l'étage de détection d'un pipeline. Il lit un texte et renvoie les PII qu'il y trouve. Tout détecteur satisfait le port `AnyDetector` et renvoie une liste de `Detection`, quel que soit le backend qu'il enveloppe.

```python
from piighost.components.detector import (
    ChunkedDetector,
    CompositeDetector,
    ExactMatchDetector,
    LLMDetector,
    RegexDetector,
)
from piighost.components.detector.ner import (
    Gliner2Detector,
    SpacyDetector,
    TransformersDetector,
)
```

Chaque détecteur NER a besoin de son propre extra (`gliner2`, `spacy`, `transformers`). `LLMDetector` a besoin de l'extra `llm` et d'un paquet fournisseur.

---

## `AnyDetector` (protocole)

Le port que tout détecteur implémente. Une seule méthode asynchrone, donc une implémentation peut attendre une I/O comme un serveur de modèle ou une API LLM sans bloquer le pipeline.

```python
class AnyDetector(Protocol):
    async def detect(self, text: str) -> list[Detection]: ...
```

`detect` renvoie les détections dans un ordre quelconque. Les chevauchements et les doublons sont résolus par les étages suivants du pipeline, pas par le détecteur.

### `Detection`

Chaque détecteur renvoie une liste de `Detection`, un dataclass gelé qui porte l'emplacement de la correspondance, le texte trouvé, son label et sa confiance.

| Attribut | Type | Description |
|----------|------|-------------|
| `span` | `Span` | L'emplacement de la détection, en intervalle semi-ouvert |
| `text` | `str` | La sous-chaîne trouvée |
| `label` | `str` | La catégorie de PII, par exemple `PERSON` ou `EMAIL` |
| `confidence` | `float` | La confiance du détecteur, dans l'intervalle fermé 0 à 1 |

---

## `RegexDetector`

Trouve les PII en appliquant un pattern regex par label. Chaque pattern est compilé une fois à la construction. `detect` émet une détection par correspondance sans chevauchement, à une confiance fixe de 1.0.

Il ne porte aucun validateur de somme de contrôle, donc il correspond sur la forme seule. Une valeur structurée abîmée par un OCR est conservée plutôt que rejetée, car rejeter une vraie valeur reviendrait à la laisser fuiter.

### Constructeur

```python
RegexDetector(patterns: dict[str, str])
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `patterns` | `dict[str, str]` | Correspondance d'un label de PII vers le pattern regex à appliquer (requis) |

```python
from piighost.components.detector import RegexDetector

detector = RegexDetector({"EMAIL": r"[\w.+-]+@[\w.-]+\.\w{2,}"})
detections = await detector.detect("write to alice@example.com")
# [Detection(span=Span(9, 26), text="alice@example.com", label="EMAIL", confidence=1.0)]
```

---

## `CompositeDetector`

Fait tourner plusieurs détecteurs sur le même texte et fusionne leurs détections. Il est lui-même un `AnyDetector`, donc il se compose avec le pipeline sans changement. Il exécute chaque enfant en parallèle et concatène leurs résultats dans l'ordre des enfants. Il ne déduplique pas. Chevauchements et doublons passent à l'étage de résolution de spans.

### Constructeur

```python
CompositeDetector(detectors: list[AnyDetector])
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `detectors` | `list[AnyDetector]` | Les détecteurs enfants à exécuter, dans l'ordre (requis) |

```python
from piighost.components.detector import CompositeDetector, RegexDetector
from piighost.components.detector.ner import Gliner2Detector

detector = CompositeDetector([
    RegexDetector({"EMAIL": r"[\w.+-]+@[\w.-]+\.\w{2,}"}),
    Gliner2Detector(model="fastino/gliner2-multi-v1", labels=["PERSON"]),
])
```

---

## `ExactMatchDetector`

Trouve les occurrences de valeurs littérales configurées. Il parcourt le texte pour chaque valeur et émet une détection par occurrence à une confiance de 1.0. Il ne porte aucun modèle et aucune dépendance optionnelle, ce qui en fait le détecteur de choix pour exercer le pipeline dans les tests.

### Constructeur

```python
ExactMatchDetector(values: dict[str, str])
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `values` | `dict[str, str]` | Correspondance d'une valeur littérale vers le label de PII à émettre pour elle (requis) |

```python
from piighost.components.detector import ExactMatchDetector

detector = ExactMatchDetector({"Patrick": "PERSON", "Lyon": "LOCATION"})
detections = await detector.detect("Patrick lives in Lyon")
```

---

## `ChunkedDetector`

Fait tourner un détecteur enveloppé sur chaque morceau d'un texte long. C'est un décorateur, lui-même un `AnyDetector`. Il découpe le texte en morceaux qui se chevauchent, exécute le détecteur enveloppé sur chacun, et reprojette chaque détection sur le texte original. Les détections strictement identiques produites par le chevauchement sont supprimées. Conflits de label et confiances différentes passent à l'étage de résolution de spans.

### Constructeur

```python
ChunkedDetector(detector: AnyDetector, splitter: AnySplitter | None = None)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `detector` | `AnyDetector` | Le détecteur exécuté sur chaque morceau (requis) |
| `splitter` | `AnySplitter \| None` | Le splitter, ou `None` pour un `RecursiveCharacterTextSplitter` par défaut |

```python
from piighost.components.detector import ChunkedDetector
from piighost.components.detector.ner import SpacyDetector

detector = ChunkedDetector(SpacyDetector(model="en_core_web_sm"))
```

---

## `LLMDetector`

Détecte les PII avec un modèle de chat LangChain via une sortie structurée. A besoin de l'extra `llm` et d'un paquet fournisseur. On demande au modèle d'extraire des paires `(text, label)` contre un schéma dont le champ label est contraint aux labels configurés. Chaque valeur extraite est ensuite localisée dans le texte source par recherche sur frontière de mot, donc une valeur inventée par le modèle mais absente du texte ne donne rien. `labels` est requis, puisque le schéma en est construit.

### Constructeur

```python
LLMDetector(
    model: BaseChatModel | str,
    labels: list[str] | dict[str, str],
    prompt: str | None = None,
    provider: str | None = None,
)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `model` | `BaseChatModel \| str` | Un modèle de chat chargé, ou un nom chargé avec `init_chat_model` (requis) |
| `labels` | `list[str] \| dict[str, str]` | Les labels à extraire, liste ou map `{emitted: internal}` (requis) |
| `prompt` | `str \| None` | Un prompt système personnalisé, ou `None` pour celui par défaut |
| `provider` | `str \| None` | Le fournisseur passé à `init_chat_model` quand `model` est un nom |

Un `prompt` personnalisé doit contenir un placeholder `{labels}` et, selon le format f-string de LangChain, doubler toute autre accolade littérale en `{{` ou `}}`.

```python
from piighost.components.detector import LLMDetector

detector = LLMDetector(
    model="gpt-4o-mini",
    labels=["PERSON", "EMAIL"],
    provider="openai",
)
```

---

## Détecteurs NER

Les trois détecteurs adossés à un modèle étendent `BaseNERDetector`, qui gère la correspondance et le filtrage des labels (voir plus bas). Chacun a besoin de son propre extra et prend un modèle chargé ou un nom de modèle à charger.

### `Gliner2Detector`

Un modèle GLiNER2 zero-shot. A besoin de l'extra `gliner2`. `labels` est requis, car GLiNER2 est interrogé avec les labels internes. Un `model` en `str` est chargé avec `GLiNER2.from_pretrained`.

```python
Gliner2Detector(
    model: GLiNER2 | str,
    labels: list[str] | dict[str, str],
    threshold: float = 0.5,
    max_concurrency: int | None = None,
)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `model` | `GLiNER2 \| str` | Un modèle chargé, ou un nom chargé avec `from_pretrained` (requis) |
| `labels` | `list[str] \| dict[str, str]` | Les labels à interroger, liste ou map `{emitted: internal}` (requis) |
| `threshold` | `float` | La confiance à partir de laquelle une entité est conservée |
| `max_concurrency` | `int \| None` | Plafond d'inférences concurrentes, ou `None` pour sans limite |

### `SpacyDetector`

Un modèle NER spaCy. A besoin de l'extra `spacy`. `labels` est optionnel. Omis, chaque entité produite par spaCy est conservée avec son label spaCy. Un `model` en `str` est chargé avec `spacy.load`.

```python
SpacyDetector(
    model: Language | str,
    labels: list[str] | dict[str, str] | None = None,
    max_concurrency: int | None = None,
)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `model` | `Language \| str` | Un modèle chargé, ou un nom chargé avec `spacy.load` (requis) |
| `labels` | `list[str] \| dict[str, str] \| None` | Les labels à mapper et filtrer, ou `None` pour garder chaque label natif |
| `max_concurrency` | `int \| None` | Plafond d'inférences concurrentes, ou `None` pour sans limite |

### `TransformersDetector`

Un pipeline de classification de tokens Hugging Face. A besoin de l'extra `transformers`. `labels` est optionnel, gardé natif s'il est omis. Un `pipeline` en `str` est chargé comme un pipeline `ner`. Une entité qui score sous `threshold` est rejetée.

```python
TransformersDetector(
    pipeline: TokenClassificationPipeline | str,
    labels: list[str] | dict[str, str] | None = None,
    threshold: float = 0.0,
    max_concurrency: int | None = None,
)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `pipeline` | `TokenClassificationPipeline \| str` | Un pipeline construit, ou un nom de modèle chargé comme pipeline `ner` (requis) |
| `labels` | `list[str] \| dict[str, str] \| None` | Les labels à mapper et filtrer, ou `None` pour garder chaque label natif |
| `threshold` | `float` | Le score sous lequel une entité détectée est rejetée |
| `max_concurrency` | `int \| None` | Plafond d'inférences concurrentes, ou `None` pour sans limite |

### Correspondance des labels

`BaseNERDetector` normalise l'argument `labels` en une map externe vers interne, puis mappe et filtre les détections produites par le modèle. Il distingue le label qu'un modèle utilise nativement du label émis dans `Detection.label`.

- Une liste, `["PERSON", "LOCATION"]`, mappe chaque label vers lui-même.
- Une map, `{"PER": "PERSON"}`, ne garde que les détections dont le label natif est une clé et réétiquette chacune vers sa valeur. Un label natif absent de la map est rejeté.
- `None` ou une map vide n'applique aucune correspondance, donc chaque détection est gardée avec le label donné par le modèle.

Deux labels externes mappant vers un même label interne lèvent `LabelMappingError`, car la recherche inverse serait ambiguë.

```python
from piighost.components.detector.ner import TransformersDetector

detector = TransformersDetector(
    pipeline="dslim/bert-base-NER",
    labels={"PER": "PERSON", "LOC": "LOCATION"},
)
```

---

## Catalogues de patterns

Ensembles de patterns regex réutilisables pour `RegexDetector`. Chaque catalogue est un `dict[str, str]` simple qui associe un label de PII à un pattern regex. Les patterns correspondent sur la forme seule, sans validation de somme de contrôle.

```python
from piighost.components.detector.patterns import (
    EU_PATTERNS,
    FR_PATTERNS,
    GENERIC_PATTERNS,
    US_PATTERNS,
)
```

Passez un catalogue à un `RegexDetector`, ou fusionnez-en plusieurs par fusion de dict, un pattern en ligne sur le même label prenant le dessus.

```python
from piighost.components.detector import RegexDetector
from piighost.components.detector.patterns import FR_PATTERNS, GENERIC_PATTERNS

detector = RegexDetector({**GENERIC_PATTERNS, **FR_PATTERNS})
```

<div class="wide-table" markdown="1">

| Catalogue | Import | Labels |
|-----------|--------|--------|
| Générique | `GENERIC_PATTERNS` | `EMAIL`, `URL`, `IPV4`, `CREDIT_CARD` |
| US | `US_PATTERNS` | `US_SSN`, `US_PHONE`, `US_ZIP` |
| EU | `EU_PATTERNS` | `IBAN` |
| France | `FR_PATTERNS` | `FR_PHONE`, `FR_IBAN`, `FR_NIR`, `FR_SIRET` |

</div>

Les labels de `GENERIC_PATTERNS` ne dépendent d'aucun pays. Les autres sont préfixés (`US_`, `FR_`) pour ne pas se confondre quand les catalogues sont fusionnés. `EU_PATTERNS` porte l'IBAN ISO 13616 partagé entre les États membres. Pour des numéros propres à un pays, utilisez un catalogue par pays.

### Tirer les catalogues depuis une config

Une config de détecteur regex tire les catalogues par nom via `catalogs`, parmi `generic`, `us`, `eu`, `fr`. Les catalogues nommés fusionnent d'abord, puis les `patterns` en ligne, donc un pattern en ligne l'emporte sur un pattern de catalogue sur le même label. Une config de détecteur regex a besoin d'au moins un pattern en ligne ou un catalogue.

```toml
[detector]
type = "regex"
catalogs = ["generic", "fr"]

[detector.patterns]
INTERNAL_ID = "EMP-\\d{6}"
```

---

## Voir aussi

- [Référence Pipeline](pipeline.md) pour le pipeline qui pilote le détecteur.
- [Détecteurs prêts à l'emploi](../examples/detectors.md) pour composer les catalogues en pratique.
- [Configuration TOML](../configuration/toml.md) pour la construction déclarative.
- [Étendre PIIGhost](../extending.md) pour écrire son propre détecteur.
