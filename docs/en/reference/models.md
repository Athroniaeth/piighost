---
icon: lucide/boxes
---

# Data models reference

Module: `piighost.models`

The value objects the pipeline stages exchange. A detector returns `Detection`, the linker groups detections into `Entity`, both carry their position as a `Span`, and a splitter cuts a long text into `Chunk`. Pure Python, no external dependency.

```python
from piighost.models import Chunk, Detection, Entity, Span
```

`Detection`, `Entity` and `Span` are also re-exported from the package root, so `from piighost import Detection` resolves the same class.

---

## The dataclass contract

The four models are declared `@dataclass(frozen=True, slots=True)`. `Span` and `Detection` add `order=True`. For a caller that means:

- **Immutable.** Assigning to a field raises `FrozenInstanceError`. Build a modified copy with `dataclasses.replace`, which is how `ChunkedDetector` remaps a chunk detection onto the original text.
- **Slotted.** An instance carries no `__dict__`, so no attribute outside the declared fields can be set on it.
- **Compared by value and hashable.** Two instances with equal fields are equal and hash alike, which lets a `Detection` sit in a set and an `Entity` key the `tokens` mapping of an `Anonymization`.
- **Sortable for `Span` and `Detection` only.** Both compare in field order. `Entity` and `Chunk` declare no ordering, so comparing two of them raises `TypeError`.
- **Validated at construction.** Every invariant is checked in `__post_init__`, so an invalid instance never exists. Each exception derives from `PIIGhostError`.

```python
from dataclasses import replace

from piighost.models import Detection, Span

detection = Detection(span=Span(0, 7), text="Patrick", label="PERSON", confidence=1.0)
moved = replace(detection, span=detection.span.shift(10))
# moved == Detection(span=Span(10, 17), text="Patrick", label="PERSON", confidence=1.0)
```

---

## `Span`

Module: `piighost.models.span`

A half-open character range over a text, `[start, end)`, mirroring the slice `text[start:end]`. It is the geometric primitive the detect and render stages share.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `start` | `int` | Inclusive start offset, 0 or greater |
| `end` | `int` | Exclusive end offset, strictly greater than `start` |

Ordering is `(start, end)`, so a list of spans sorts left to right. The render stage relies on that to apply its edits without shifting an offset it has not processed yet.

### Properties

#### `length` (property)

The number of characters covered, `end - start`. `len(span)` returns the same value.

### Methods

#### `overlaps(other) -> bool`

Whether the two ranges share at least one character. Half-open semantics mean two adjacent ranges such as `Span(0, 5)` and `Span(5, 10)` do not overlap.

#### `contains(other) -> bool`

Whether `other` is fully enclosed by this span, bounds included.

#### `shift(offset) -> Span`

A copy translated by `offset` characters. It remaps a span found on a chunk or on normalized text back onto the original text. A shift that would push `start` below zero raises through the constructor rather than clamp, so the bug surfaces.

#### `extract(text) -> str`

The substring of `text` this span covers.

```python
from piighost.models import Span

span = Span(9, 26)
span.length                                  # 17
span.extract("write to alice@example.com")   # "alice@example.com"
span.overlaps(Span(26, 30))                  # False, the two ranges are adjacent
span.shift(-9)                               # Span(0, 17)
```

### Validation

| Exception | Condition |
|-----------|-----------|
| `NegativeSpanStartError` | `start` is negative |
| `SpanOrderingError` | `end` is not strictly greater than `start`, an empty or a reversed range |

Both derive from `SpanError`. An empty range is refused because a PII detection always covers at least one character.

---

## `Detection`

Module: `piighost.models.detection`

One PII occurrence a detector found. A span carrying the matched text, a label and a confidence.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `span` | `Span` | Where the detection sits in the text, as a half-open range |
| `text` | `str` | The matched substring |
| `label` | `str` | The PII category, for example `PERSON` or `EMAIL` |
| `confidence` | `float` | Detector confidence, in the closed range 0 to 1 |

Ordering is `(span, text, label, confidence)`, so detections sort by position first, which the overlap-resolver stage relies on.

### Methods

#### `overlaps(other) -> bool`

Whether this detection's span overlaps the other's. It delegates to `Span.overlaps`.

#### `to_dict() -> dict[str, str | int | float]`

The detection as a flat, JSON-ready dict, the span flattened into `start` and `end`. The shape is one level, so a store or a wire format serializes it without knowing the model. The CLI prints these under `piighost anonymize --json`.

#### `from_dict(data) -> Detection` (classmethod)

A detection rebuilt from the flat dict `to_dict` produces.

```python
from piighost.models import Detection, Span

detection = Detection(span=Span(0, 7), text="Patrick", label="PERSON", confidence=1.0)
detection.to_dict()
# {"start": 0, "end": 7, "text": "Patrick", "label": "PERSON", "confidence": 1.0}
```

### Validation

| Exception | Condition |
|-----------|-----------|
| `ConfidenceError` | `confidence` falls outside the closed range 0 to 1 |

It derives from `DetectionError`.

---

## `Entity`

Module: `piighost.models.entity`

The detections identified as the same PII value, grouped by the link stage. The group shares one token and restores to one value.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `detections` | `tuple[Detection, ...]` | The occurrences the entity groups, at least one, all sharing a label |

### Properties

#### `label` (property)

The shared PII label of the grouped detections.

#### `text` (property)

The canonical value, taken from the first occurrence.

#### `spans` (property)

The span of every occurrence, in detection order.

The label, the canonical text and the spans are derived from the detections rather than stored, so nothing drifts out of sync and the value is held in one place.

```python
from piighost.models import Detection, Entity, Span

first = Detection(span=Span(0, 7), text="Patrick", label="PERSON", confidence=1.0)
second = Detection(span=Span(20, 27), text="Patrick", label="PERSON", confidence=0.8)
entity = Entity(detections=(first, second))

entity.label   # "PERSON"
entity.text    # "Patrick"
entity.spans   # (Span(0, 7), Span(20, 27))
```

### Validation

| Exception | Condition |
|-----------|-----------|
| `EmptyEntityError` | No detection is given |
| `MixedLabelError` | The detections do not all share one label |

Both derive from `EntityError`.

---

## `Chunk`

Module: `piighost.models.chunk`

A contiguous slice of a larger text, with its offset in that text.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `text` | `str` | The chunk substring, a slice of the original text |
| `start` | `int` | The offset of the chunk in the original text |

### Properties

#### `end` (property)

The exclusive end offset in the original text, `start + len(text)`.

A splitter produces chunks. Every `AnySplitter` in `piighost.text` returns them in order, and `RecursiveCharacterTextSplitter` overlaps consecutive ones so a value sitting on a boundary is still seen whole in one chunk. `ChunkedDetector` runs its wrapped detector on `chunk.text`, then shifts each detection by `chunk.start` to remap it onto the original text.

```python
from piighost.text import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(chunk_size=20, chunk_overlap=5)
chunks = splitter.split("Patrick lives in Lyon and works in Paris.")
# chunks[0] == Chunk(text="Patrick lives in", start=0)
# chunks[1] == Chunk(text="in Lyon and works in", start=14)
```

---

## Models defined elsewhere

Two more frozen dataclasses travel with the pipeline, each documented on the page of the component that produces it.

| Model | Module | Page |
|-------|--------|------|
| `Anonymization` | `piighost.components.anonymizer` | [Anonymizer reference](anonymizer.md) |
| `Forgotten` | `piighost.conversation_memory` | [Conversation memory reference](memory.md) |

---

## See also

- [Detectors reference](detectors.md) for the detectors that produce a `Detection`.
- [Pipeline reference](pipeline.md) for the stages these models pass through.
- [Extending PIIGhost](../extending.md) for building them in your own component.
- [CLI reference](cli.md) for the JSON output built from `to_dict`.
