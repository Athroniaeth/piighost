---
title: Anonymizer — Référence API
---

# Anonymizer

`src/aegra/anonymizer.py`

Composant bas niveau responsable de la détection NER et du remplacement par placeholders. Peut être utilisé indépendamment du middleware pour des cas d'usage custom.

---

## Types de données

### `GlinerEntity`

```python
class GlinerEntity(TypedDict):
    text: Required[str]
    confidence: NotRequired[float]
    start: NotRequired[int]
    end: NotRequired[int]
```

Dict brut retourné par la bibliothèque GLiNER2.

---

### `NamedEntity`

```python
@dataclass
class NamedEntity:
    text: str
    entity_type: str
    confidence: float
    start: Optional[int] = None
    end: Optional[int] = None
    anon_start: Optional[int] = None
    anon_end: Optional[int] = None
```

Entité enrichie produite par le pipeline d'anonymisation.

| Attribut | Description |
|----------|-------------|
| `text` | Surface form de l'entité dans le texte source |
| `entity_type` | Label de catégorie (`"person"`, `"location"`, etc.) |
| `confidence` | Score de confiance GLiNER2, entre 0 et 1 |
| `start` / `end` | Offsets dans le texte **original** (inclusif / exclusif) |
| `anon_start` / `anon_end` | Offsets du placeholder dans le texte **anonymisé** |

---

### `Placeholder`

```python
class Placeholder(str): ...
```

Sous-classe de `str` représentant un jeton d'anonymisation, ex : `<PERSON_1>`.

Format : `<TYPE_N>` où `TYPE` est le label en majuscules et `N` l'index 1-based dans ce type.

---

### `ThreadID`

```python
class ThreadID(str): ...
```

Identifiant de fil de conversation. Généré automatiquement via UUID si non fourni.

---

## Fonctions utilitaires

### `build_placeholder(label, index)`

```python
def build_placeholder(label: str, index: int) -> Placeholder
```

Construit un jeton placeholder.

```python
build_placeholder("person", 1)   # → "<PERSON_1>"
build_placeholder("location", 3) # → "<LOCATION_3>"
```

---

### `resolve_thread_id(thread_id)`

```python
def resolve_thread_id(thread_id: Optional[str]) -> ThreadID
```

Retourne un `ThreadID`, en générant un UUID si `thread_id` est `None`.

---

## Classe `Anonymizer`

```python
class Anonymizer:
    def __init__(
        self,
        extractor: GLiNER2,
        entity_types: Optional[List[str]] = None,
        min_confidence: float = 0.5,
    )
```

| Paramètre | Défaut | Description |
|-----------|--------|-------------|
| `extractor` | — | Instance GLiNER2 (ex: `GLiNER2.from_pretrained("fastino/gliner2-base-v1")`) |
| `entity_types` | `["company", "person", "product", "location"]` | Labels à détecter |
| `min_confidence` | `0.5` | Score minimum pour qu'une entité soit prise en compte |

---

### `detect_entities(text)`

```python
def detect_entities(self, text: str) -> List[NamedEntity]
```

Détecte les entités dans `text` via GLiNER2 et filtre par `min_confidence`.

**Retourne :** Liste de `NamedEntity` triés par ordre d'apparition.

---

### `assign_placeholders(detections, existing_vocab)`

```python
def assign_placeholders(
    self,
    detections: List[NamedEntity],
    existing_vocab: Optional[Dict[str, Placeholder]] = None,
) -> Dict[Placeholder, List[NamedEntity]]
```

Assigne un placeholder à chaque entité unique.

**Comportement :**

- Deux occurrences du même texte → même placeholder
- Textes distincts d'un même type → indices croissants (`<PERSON_1>`, `<PERSON_2>`...)
- Si `existing_vocab` est fourni : les textes déjà connus réutilisent leur placeholder ; les nouveaux indices partent après les déjà assignés

**Retourne :** `Dict[Placeholder → List[NamedEntity]]`

---

### `expand_placeholders(text, placeholders)`

```python
def expand_placeholders(
    self,
    text: str,
    placeholders: Dict[Placeholder, List[NamedEntity]],
) -> Dict[Placeholder, List[NamedEntity]]
```

Balaye le texte complet pour trouver des occurrences supplémentaires non détectées par GLiNER2.

!!! note
    GLiNER2 ne détecte souvent que la première occurrence d'une entité. Cette étape garantit une couverture complète via `re.finditer`.

---

### `replace_with_placeholders(text, placeholders)`

```python
def replace_with_placeholders(
    self,
    text: str,
    placeholders: Dict[Placeholder, List[NamedEntity]],
) -> str
```

Remplace les spans détectés par leurs jetons.

**Algorithme :**

1. Collecte tous les candidats `(start, end, placeholder, confidence)`
2. Trie par confiance décroissante, puis par longueur de span décroissante
3. Greedy : accepte les spans non chevauchantes
4. Applique les remplacements en sens inverse (index décroissants) pour préserver la cohérence des offsets

---

### `compute_anonymized_spans(anonymized_text, placeholders)`

```python
def compute_anonymized_spans(
    self,
    anonymized_text: str,
    placeholders: Dict[Placeholder, List[NamedEntity]],
) -> Dict[Placeholder, List[NamedEntity]]
```

Calcule `anon_start` / `anon_end` de chaque entité en scannant le texte anonymisé.

---

### `anonymize(text, thread_id)`

```python
def anonymize(
    self,
    text: str,
    thread_id: Optional[str] = None,
) -> tuple[str, Dict[Placeholder, List[NamedEntity]]]
```

Pipeline complet d'anonymisation avec persistance du vocabulaire par thread.

```python
anon_text, placeholders = anonymizer.anonymize(
    "Tim Cook habite à Cupertino.",
    thread_id="thread-001",
)
# anon_text → "<PERSON_1> habite à <LOCATION_1>."
```

**Retourne :** `(texte_anonymisé, placeholders)`

---

### `deanonymize(text, placeholders)`

```python
def deanonymize(
    self,
    text: str,
    placeholders: Dict[Placeholder, List[NamedEntity]],
) -> str
```

Restaure les valeurs originales en remplaçant les jetons.

Les occurrences multiples d'un même jeton sont restituées dans l'ordre d'apparition original (tri par `entity.start`), ce qui permet de gérer des entités avec des surfaces légèrement différentes.

---

### `anonymize_messages(messages, thread_id)`

```python
def anonymize_messages(
    self,
    messages: list[AnyMessage],
    thread_id: Optional[str] = None,
) -> tuple[list[AnyMessage], Dict[Placeholder, List[NamedEntity]]]
```

Anonymise une liste de messages LangChain en préservant le contexte de thread.

!!! warning
    Seuls les messages avec `content` de type `str` sont supportés.

---

### `deanonymize_messages(messages, thread_id, placeholders)`

```python
def deanonymize_messages(
    self,
    messages: list[AnyMessage],
    thread_id: Optional[str] = None,
    placeholders: Optional[Dict[Placeholder, List[NamedEntity]]] = None,
) -> list[AnyMessage]
```

Désanonymise une liste de messages. Priorité : `placeholders` explicites > lookup par `thread_id`.

---

## Exemple complet

```python
from gliner2 import GLiNER2
from aegra.anonymizer import Anonymizer

extractor = GLiNER2.from_pretrained("fastino/gliner2-base-v1")
anonymizer = Anonymizer(extractor, min_confidence=0.5)

# Tour 1
anon1, ph1 = anonymizer.anonymize("Pierre habite à Lyon.", thread_id="conv-1")
# anon1 → "<PERSON_1> habite à <LOCATION_1>."

# Tour 2 — Pierre et Lyon sont réutilisés
anon2, ph2 = anonymizer.anonymize("Pierre est-il à Lyon aujourd'hui ?", thread_id="conv-1")
# anon2 → "<PERSON_1> est-il à <LOCATION_1> aujourd'hui ?"

# Désanonymisation
original = anonymizer.deanonymize(anon1, ph1)
# original → "Pierre habite à Lyon."
```
