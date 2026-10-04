---
icon: lucide/scan-text
---

# Référence Anonymizer

Module : `piighost.components.anonymizer`

L'anonymizer est l'étage de rendu d'un pipeline. Il prend les entités liées et le texte source, demande à une placeholder factory un jeton par entité, et réécrit le texte pour que chaque occurrence d'une entité devienne son jeton. Il inverse aussi la correspondance pour restaurer l'original.

---

## `Anonymization`

Le résultat de la dé-identification d'un texte. Le texte réécrit associé au jeton qui a remplacé chaque entité. Un dataclass gelé.

```python
@dataclass(frozen=True, slots=True)
class Anonymization(Generic[PreservationT_co]):
    text: str
    tokens: Mapping[Entity, PreservationT_co]
```

| Attribut | Type | Description |
|----------|------|-------------|
| `text` | `str` | Le texte avec chaque occurrence d'entité remplacée par son jeton |
| `tokens` | `Mapping[Entity, str]` | Le jeton qui a remplacé chaque entité |

Le type de la correspondance dit ce que la factory préserve. Un appelant peut donc l'inverser pour restaurer l'original, mais seulement quand les jetons préservent l'identité.

---

## `Anonymizer`

Remplace les spans de chaque entité par le jeton qu'une factory lui assigne. Il édite les spans de gauche à droite en une passe. Cette passe unique reste correcte parce que les étages en amont laissent les spans sans chevauchement. Aucune édition ne décale donc un offset dont une autre a encore besoin. Sans état. Rien n'est retenu d'un appel à l'autre.

### Constructeur

```python
Anonymizer(ph_factory: AnyPlaceholderFactory[PreservationT], escape_existing_tokens: bool = True)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `ph_factory` | `AnyPlaceholderFactory[PreservationT]` | La placeholder factory qui assigne un jeton à chaque entité (requis) |
| `escape_existing_tokens` | `bool` | Neutralise les jetons saisis par l'utilisateur dans l'entrée pour qu'ils ne puissent pas se faire passer pour des jetons de la factory et détourner une valeur à la restauration. Ne s'applique que quand la factory émet une grammaire délimitée reconnaissable, c'est-à-dire des jetons encadrés de délimiteurs comme `<<PERSON:1>>`. Vaut `True` par défaut |

La factory est exposée ensuite via la propriété `factory`.

### Méthodes

#### `anonymize(text, entities) -> Anonymization`

Assigne un jeton à chaque entité, rend le texte contre ces jetons, et renvoie les deux dans une `Anonymization`.

```python
--8<-- "snippets/reference_anonymizer.py:anonymize"
```

#### `create(entities) -> Mapping[Entity, str]`

Renvoie le jeton que chaque entité obtient, sans toucher au texte. Séparer l'assignation des jetons du rendu permet à un appelant d'assigner les jetons sur un ensemble d'entités, comme toute une conversation, puis de rendre plusieurs textes contre ces mêmes jetons.

```python
--8<-- "snippets/reference_anonymizer.py:create"
```

#### `render(text, entities, tokens) -> str`

Renvoie `text` avec les spans de chaque entité remplacés par le jeton donné. Utilisé par le pipeline de conversation pour rendre un message contre des jetons assignés sur toute la conversation.

Avec `escape_existing_tokens` actif et une factory à délimiteurs, `render` neutralise tout jeton que l'utilisateur a saisi dans le texte laissé tel quel entre les spans d'entités. Il y insère un espace de largeur nulle, pour que ce jeton ne puisse pas être restauré comme un vrai jeton. Les spans d'entités et leurs offsets restent intacts.

Lève `OverlappingSpansError` quand deux spans se chevauchent. L'étage de résolution des chevauchements doit s'exécuter avant. Un chevauchement qui arrive jusqu'ici fait donc échouer l'appel, plutôt que d'introduire un fragment en clair d'une détection dans une autre.

```python
--8<-- "snippets/reference_anonymizer.py:render"
```

#### `deanonymize(text, tokens) -> str`

Renvoie le texte avec chaque jeton connu remplacé par la valeur de son entité, en lisant la correspondance à l'envers. Tout texte portant ces jetons est restauré, y compris un texte que le pipeline n'a jamais produit. Les jetons absents de la correspondance sont laissés intacts.

La restauration n'est sans ambiguïté que si les jetons préservent l'identité, car deux entités partageant un même jeton se confondent en une seule valeur.

```python
--8<-- "snippets/reference_anonymizer.py:deanonymize"
```

---

## `AnyAnonymizer` (protocole)

Le port que tout anonymizer implémente. Il est générique sur ce que ses jetons préservent. Un consommateur comme le middleware peut donc, dès la vérification de types, exiger un anonymizer dont les jetons préservent l'identité et rejeter celui dont les jetons ne la préservent pas.

```python
@runtime_checkable
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

Le template que `Anonymizer` étend. Il tient les étapes partagées, c'est-à-dire demander à la factory un jeton par entité via `create`, les composer en une `Anonymization` dans `anonymize`, et inverser la correspondance dans `deanonymize`. Une sous-classe définit `render`, la seule étape qui varie. `render` est la règle qui réécrit le texte à partir des entités et de leurs jetons.

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
- [Placeholder factories](../placeholder-factories.md) pour les jetons que l'anonymizer émet.
- [Étendre piighost](../extending.md) pour écrire son propre anonymizer.
