---
icon: lucide/scan-text
---

# Anonymizer reference

Module: `piighost.components.anonymizer`

The anonymizer is the render stage of a pipeline. It takes the linked entities and the source text, asks a placeholder factory for one token per entity, and rewrites the text so every occurrence of an entity becomes its token. It also reverses the mapping to restore the original.

---

## `Anonymization`

The result of anonymizing a text. The rewritten text paired with the token each entity was replaced with. A frozen dataclass.

```python
@dataclass(frozen=True, slots=True)
class Anonymization(Generic[PreservationT_co]):
    text: str
    tokens: Mapping[Entity, PreservationT_co]
```

| Attribute | Type | Description |
|-----------|------|-------------|
| `text` | `str` | The text with every entity occurrence replaced by its token |
| `tokens` | `Mapping[Entity, str]` | The token each entity was replaced with |

The mapping is typed by what the factory preserves, so a caller can reverse it to deanonymize only when the tokens preserve identity.

---

## `Anonymizer`

Replaces each entity's spans with the token a factory assigns it. It edits the spans left to right in one pass, which stays correct because upstream stages leave them non-overlapping, so no edit shifts an offset another edit still needs. Stateless: no internal state between calls.

### Constructor

```python
Anonymizer(ph_factory: AnyPlaceholderFactory, escape_existing_tokens: bool = True)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `ph_factory` | `AnyPlaceholderFactory` | The placeholder factory that assigns a token to each entity (required) |
| `escape_existing_tokens` | `bool` | Neutralizes tokens the user typed in the input so they cannot masquerade as factory tokens and hijack a value at restoration. Only applies when the factory emits a recognizable delimited grammar. Defaults to `True` |

The factory is exposed afterwards as the `factory` property.

### Methods

#### `anonymize(text, entities) -> Anonymization`

Assigns a token to each entity, renders the text against those tokens, and returns both as an `Anonymization`.

```python
from piighost.components.anonymizer import Anonymizer
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.models import Detection, Entity, Span

factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)

detection = Detection(span=Span(0, 7), text="Patrick", label="PERSON", confidence=0.9)
entity = Entity(detections=(detection,))

result = anonymizer.anonymize("Patrick is nice", [entity])
# result.text == "<<PERSON:1>> is nice"
# result.tokens == {entity: "<<PERSON:1>>"}
```

#### `create(entities) -> Mapping[Entity, str]`

Returns the token each entity maps to, without touching any text. Splitting token assignment out of rendering lets a caller assign tokens over one entity set, such as a whole conversation, then render several texts against those same tokens.

```python
tokens = anonymizer.create([entity])
# {entity: "<<PERSON:1>>"}
```

#### `render(text, entities, tokens) -> str`

Returns `text` with each entity's spans replaced by its given token. Used by the thread pipeline to render one message against tokens assigned over the whole thread.

With `escape_existing_tokens` on and a delimited factory, `render` neutralizes any token the user typed in the literal runs between entity spans by splicing a zero-width space into it, so it cannot be restored as a real token. The entity spans and their offsets are untouched.

Raises `OverlappingSpansError` when two spans overlap. The overlap-resolver stage must run first, so an overlap here fails closed rather than splice a clear fragment of one detection into another.

```python
rendered = anonymizer.render("Patrick is nice", [entity], tokens)
# "<<PERSON:1>> is nice"
```

#### `deanonymize(text, tokens) -> str`

Returns the text with every known token replaced by its entity's value, reading the mapping in reverse. Any text carrying those tokens is restored, including one the pipeline never produced. Tokens absent from the mapping are left untouched.

Restoration is unambiguous only when the tokens preserve identity, since two entities sharing one token collapse to a single value.

```python
original = anonymizer.deanonymize("<<PERSON:1>> is nice", result.tokens)
# "Patrick is nice"
```

---

## `AnyAnonymizer` (protocol)

The port every anonymizer implements. Generic on what its tokens preserve, so a consumer such as the middleware can require an anonymizer whose tokens preserve identity and reject one whose tokens do not, at type-check time.

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

The template `Anonymizer` extends. It holds the shared steps: ask the factory for one token per entity through `create`, compose them into an `Anonymization` in `anonymize`, and reverse the mapping in `deanonymize`. A subclass defines `render`, the only step that varies, the rule that rewrites the text given the entities and their tokens.

```python
class BaseAnonymizer(ABC, Generic[PreservationT]):
    def __init__(self, ph_factory: AnyPlaceholderFactory[PreservationT]) -> None: ...

    @abstractmethod
    def render(
        self, text: str, entities: list[Entity], tokens: Mapping[Entity, str]
    ) -> str: ...
```

---

## See also

- [Pipeline reference](pipeline.md) for the pipeline that drives the anonymizer.
- [Placeholder factories](../placeholder-factories.md) for the tokens the anonymizer emits.
- [Extending PIIGhost](../extending.md) for writing your own anonymizer.
