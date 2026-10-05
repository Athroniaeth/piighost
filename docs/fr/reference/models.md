---
icon: lucide/boxes
---

# Référence des modèles de données

Module : `piighost.models`

Les objets valeur que les étages du pipeline échangent. Un détecteur renvoie des `Detection`, et le linker les regroupe en `Entity`. Une `Detection` et une `Entity` portent leur position sous forme de `Span`. Un splitter découpe un texte long en `Chunk`. Du Python pur, sans dépendance externe.

```python
from piighost.models import Chunk, Detection, Entity, Span
```

`Detection`, `Entity` et `Span` sont aussi ré-exportés depuis la racine du paquet, donc `from piighost import Detection` résout la même classe.

---

## Le contrat des dataclasses

Les quatre modèles sont déclarés `@dataclass(frozen=True, slots=True)`. `Span` et `Detection` ajoutent `order=True`. Pour un appelant, cela veut dire :

- **Immuable.** Affecter un champ lève `FrozenInstanceError`. Construisez une copie modifiée avec `dataclasses.replace`, comme `ChunkedDetector` le fait pour reporter une détection de chunk sur le texte original.
- **Sans dictionnaire d'attributs.** Une instance ne porte pas de `__dict__`, donc aucun attribut hors des champs déclarés ne peut lui être posé.
- **Comparé par valeur et hachable.** Deux instances aux champs égaux sont égales et ont le même hash. Une `Detection` peut donc vivre dans un set, et une `Entity` servir de clé dans la correspondance `tokens` d'une `Anonymization`.
- **Triable pour `Span` et `Detection` seulement.** Les deux se comparent dans l'ordre de leurs champs. `Entity` et `Chunk` ne déclarent aucun ordre, donc comparer deux d'entre eux lève `TypeError`.
- **Validé à la construction.** Chaque invariant est vérifié dans `__post_init__`, donc une instance invalide n'existe jamais. Chaque exception dérive de `PIIGhostError`.

```python
--8<-- "snippets/reference_models.py:replace"
```

---

## `Span`

Module : `piighost.models.span`

Un intervalle de caractères semi-ouvert sur un texte, `[start, end)`, qui reprend la tranche `text[start:end]`. C'est la primitive géométrique partagée par les étages de détection et de rendu.

### Champs

| Champ | Type | Description |
|-------|------|-------------|
| `start` | `int` | Offset de début inclus, supérieur ou égal à 0 |
| `end` | `int` | Offset de fin exclu, strictement supérieur à `start` |

Le tri se fait sur `(start, end)`, donc une liste de spans s'ordonne de gauche à droite. L'étage de rendu s'appuie sur cet ordre pour appliquer ses éditions sans décaler un offset qu'il n'a pas encore traité.

### Propriétés

#### `length` (propriété)

Le nombre de caractères couverts, `end - start`. `len(span)` renvoie la même valeur.

### Méthodes

#### `overlaps(other) -> bool`

Si les deux intervalles partagent au moins un caractère. La sémantique semi-ouverte fait que deux intervalles adjacents comme `Span(0, 5)` et `Span(5, 10)` ne se chevauchent pas.

#### `contains(other) -> bool`

Si `other` est entièrement inclus dans ce span, bornes comprises.

#### `shift(offset) -> Span`

Une copie translatée de `offset` caractères. Elle reporte un span trouvé sur un chunk ou sur du texte normalisé vers le texte original. Un décalage qui pousserait `start` sous zéro lève une erreur dans le constructeur au lieu de rogner le span. Le bug remonte ainsi.

#### `extract(text) -> str`

La sous-chaîne de `text` que ce span couvre.

```python
--8<-- "snippets/reference_span.fr.py:example"
```

### Validation

| Exception | Condition |
|-----------|-----------|
| `NegativeSpanStartError` | `start` est négatif |
| `SpanOrderingError` | `end` n'est pas strictement supérieur à `start`, c'est-à-dire un intervalle vide ou inversé |

Les deux dérivent de `SpanError`. Un intervalle vide est refusé parce qu'une détection couvre toujours au moins un caractère.

---

## `Detection`

Module : `piighost.models.detection`

Une occurrence de donnée confidentielle trouvée par un détecteur. Elle porte un span, le texte trouvé, un label et une confiance.

### Champs

| Champ | Type | Description |
|-------|------|-------------|
| `span` | `Span` | Où la détection se situe dans le texte, sous forme d'intervalle semi-ouvert |
| `text` | `str` | La sous-chaîne trouvée |
| `label` | `str` | La catégorie de la valeur détectée, par exemple `PERSON` ou `EMAIL` |
| `confidence` | `float` | La confiance du détecteur, dans l'intervalle fermé 0 à 1 |

Le tri se fait sur `(span, text, label, confidence)`, donc les détections s'ordonnent d'abord par position. L'étage de résolution des chevauchements dépend de cet ordre.

### Méthodes

#### `overlaps(other) -> bool`

Si le span de cette détection chevauche celui de l'autre. Elle délègue à `Span.overlaps`.

#### `to_dict() -> dict[str, str | int | float]`

La détection sous forme de dict plat prêt pour JSON, le span étant aplati en `start` et `end`. La forme tient sur un niveau, donc un stockage ou un format de transport la sérialise sans connaître le modèle. La CLI imprime les détections sous cette forme avec `piighost anonymize --json`.

#### `from_dict(data) -> Detection` (méthode de classe)

Une détection reconstruite depuis le dict plat que `to_dict` produit.

```python
--8<-- "snippets/reference_models.py:to_dict"
```

### Validation

| Exception | Condition |
|-----------|-----------|
| `ConfidenceError` | `confidence` sort de l'intervalle fermé 0 à 1 |

Elle dérive de `DetectionError`.

---

## `Entity`

Module : `piighost.models.entity`

Les détections identifiées comme une même valeur, regroupées par l'étage de liaison. Le groupe partage un jeton et se restaure en une seule valeur.

### Champs

| Champ | Type | Description |
|-------|------|-------------|
| `detections` | `tuple[Detection, ...]` | Les occurrences que l'entité regroupe, au moins une, toutes de même label |

### Propriétés

#### `label` (propriété)

Le label partagé par les détections regroupées.

#### `text` (propriété)

La valeur canonique, prise sur la première occurrence.

#### `spans` (propriété)

Le span de chaque occurrence, dans l'ordre des détections.

Le label, le texte canonique et les spans sont dérivés des détections au lieu d'être stockés. Rien ne peut donc se désynchroniser, et la valeur ne vit qu'à un seul endroit.

```python
--8<-- "snippets/reference_models.py:entity"
```

### Validation

| Exception | Condition |
|-----------|-----------|
| `EmptyEntityError` | Aucune détection n'est donnée |
| `MixedLabelError` | Les détections ne partagent pas toutes un même label |

Les deux dérivent de `EntityError`.

---

## `Chunk`

Module : `piighost.models.chunk`

Une tranche contiguë d'un texte plus grand, avec son offset dans ce texte.

### Champs

| Champ | Type | Description |
|-------|------|-------------|
| `text` | `str` | La sous-chaîne du chunk, une tranche du texte original |
| `start` | `int` | L'offset du chunk dans le texte original |

### Propriétés

#### `end` (propriété)

L'offset de fin exclu dans le texte original, `start + len(text)`.

Un splitter produit les chunks. Tout `AnySplitter` de `piighost.text` renvoie les chunks dans l'ordre. `RecursiveCharacterTextSplitter` fait se recouvrir deux chunks consécutifs, pour qu'une valeur posée sur une frontière reste vue entière dans un chunk. `ChunkedDetector` exécute le détecteur qu'il enveloppe sur `chunk.text`, puis décale chaque détection de `chunk.start` pour la reporter sur le texte original.

```python
--8<-- "snippets/reference_models.py:splitter"
```

---

## Modèles définis ailleurs

Deux autres dataclasses gelées circulent avec le pipeline, chacune documentée sur la page du composant qui la produit.

| Modèle | Module | Page |
|--------|--------|------|
| `Anonymization` | `piighost.components.anonymizer` | [Référence Anonymizer](anonymizer.md) |
| `Forgotten` | `piighost.conversation_memory` | [Référence de la mémoire de conversation](memory.md) |

---

## Voir aussi

- [Référence Détecteurs](detectors.md) pour les détecteurs qui produisent une `Detection`.
- [Référence Pipeline](pipeline.md) pour les étages que ces modèles traversent.
- [Étendre piighost](../extending.md) pour les construire dans votre propre composant.
- [Interface en ligne de commande](cli.md) pour la sortie JSON bâtie sur `to_dict`.
