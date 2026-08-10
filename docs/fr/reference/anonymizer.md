---
icon: lucide/scan-text
---

# Référence Anonymizer

Module : `piighost.components.anonymizer`

L'anonymizer est l'étage de rendu d'un pipeline. Il prend les entités liées et le texte source, demande à une placeholder factory un token par entité, et réécrit le texte pour que chaque occurrence d'une entité devienne son token. Il inverse aussi la correspondance pour restaurer l'original.

---

## `Anonymization`

Le résultat de la dé-identification d'un texte. Le texte réécrit associé au token qui a remplacé chaque entité. Un dataclass gelé.

```python
@dataclass(frozen=True, slots=True)
class Anonymization(Generic[PreservationT_co]):
    text: str
    tokens: Mapping[Entity, PreservationT_co]
```

| Attribut | Type | Description |
|----------|------|-------------|
| `text` | `str` | Le texte avec chaque occurrence d'entité remplacée par son token |
| `tokens` | `Mapping[Entity, str]` | Le token qui a remplacé chaque entité |

La correspondance est typée par ce que la factory préserve, donc un appelant peut l'inverser pour désanonymiser seulement quand les tokens préservent l'identité.

---

## `Anonymizer`

Remplace les spans de chaque entité par le token qu'une factory lui assigne. Il édite les spans de gauche à droite en une passe, ce qui reste correct car les étages en amont les laissent sans chevauchement, donc aucune édition ne décale un offset dont une autre a encore besoin. Sans état. Rien n'est retenu d'un appel à l'autre.

### Constructeur

```python
Anonymizer(ph_factory: AnyPlaceholderFactory)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `ph_factory` | `AnyPlaceholderFactory` | La placeholder factory qui assigne un token à chaque entité (requis) |

La factory est exposée ensuite via la propriété `factory`.

### Méthodes

#### `anonymize(text, entities) -> Anonymization`

Assigne un token à chaque entité, rend le texte contre ces tokens, et renvoie les deux dans une `Anonymization`.

```python
from piighost.components.anonymizer import Anonymizer
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.models import Detection, Entity, Span

anonymizer = Anonymizer(LabelCounterPlaceholderFactory())

detection = Detection(span=Span(0, 7), text="Patrick", label="PERSON", confidence=0.9)
entity = Entity(detections=(detection,))

result = anonymizer.anonymize("Patrick is nice", [entity])
# result.text == "<<PERSON:1>> is nice"
# result.tokens == {entity: "<<PERSON:1>>"}
```

#### `create(entities) -> Mapping[Entity, str]`

Renvoie le token que chaque entité obtient, sans toucher au texte. Séparer l'assignation des tokens du rendu permet à un appelant d'assigner les tokens sur un ensemble d'entités, comme toute une conversation, puis de rendre plusieurs textes contre ces mêmes tokens.

```python
tokens = anonymizer.create([entity])
# {entity: "<<PERSON:1>>"}
```

#### `render(text, entities, tokens) -> str`

Renvoie `text` avec les spans de chaque entité remplacés par le token donné. Utilisé par le pipeline de thread pour rendre un message contre des tokens assignés sur tout le thread.

```python
rendered = anonymizer.render("Patrick is nice", [entity], tokens)
# "<<PERSON:1>> is nice"
```

#### `deanonymize(text, tokens) -> str`

Renvoie le texte avec chaque token connu remplacé par la valeur de son entité, en lisant la correspondance à l'envers. Tout texte portant ces tokens est restauré, y compris un texte que le pipeline n'a jamais produit. Les tokens absents de la correspondance sont laissés intacts.

La restauration n'est sans ambiguïté que si les tokens préservent l'identité, car deux entités partageant un même token se confondent en une seule valeur.

```python
original = anonymizer.deanonymize("<<PERSON:1>> is nice", result.tokens)
# "Patrick is nice"
```

---

## `AnyAnonymizer` (protocole)

Le port que tout anonymizer implémente. Générique sur ce que ses tokens préservent, donc un consommateur comme le middleware peut exiger un anonymizer dont les tokens préservent l'identité et rejeter celui dont les tokens ne la préservent pas, à la vérification de types.

```python
class AnyAnonymizer(Protocol[PreservationT_co]):
    @property
    def factory(self) -> AnyPlaceholderFactory[PreservationT_co]: ...

    def anonymize(
        self, text: str, entities: list[Entity]
    ) -> Anonymization[PreservationT_co]: ...

    def create(self, entities: list[Entity]) -> Mapping[Entity, PreservationT_co]: ...

    def render(
        self, text: str, entities: list[Entity], tokens: Mapping[Entity, str]
    ) -> str: ...

    def deanonymize(self, text: str, tokens: Mapping[Entity, str]) -> str: ...
```

---

## `BaseAnonymizer`

Le template que `Anonymizer` étend. Il tient les étapes partagées. Demander à la factory un token par entité via `create`, les composer en une `Anonymization` dans `anonymize`, et inverser la correspondance dans `deanonymize`. Une sous-classe définit `render`, la seule étape qui varie, la règle qui réécrit le texte à partir des entités et de leurs tokens.

```python
class BaseAnonymizer(ABC, Generic[PreservationT]):
    def __init__(self, ph_factory: AnyPlaceholderFactory[PreservationT]) -> None: ...

    @abstractmethod
    def render(
        self, text: str, entities: list[Entity], tokens: Mapping[Entity, str]
    ) -> str: ...
```

---

## Voir aussi

- [Référence Pipeline](pipeline.md) pour le pipeline qui pilote l'anonymizer.
- [Placeholder factories](../placeholder-factories.md) pour les tokens que l'anonymizer émet.
- [Étendre PIIGhost](../extending.md) pour écrire son propre anonymizer.
