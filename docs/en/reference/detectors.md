---
icon: lucide/list
tags:
  - Detector
  - Regex
---

# Detectors reference

Module: `piighost.components.detector`

A detector is the detect stage of a pipeline. It reads a text and returns the PII it finds. Every detector satisfies the `AnyDetector` port and returns a list of `Detection`, whatever backend it wraps.

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

The NER detectors each need their own extra (`gliner2`, `spacy`, `transformers`). `LLMDetector` needs the `llm` extra plus a provider package.

---

## `AnyDetector` (protocol)

The port every detector implements. A single async method, so an implementation can await I/O such as a model server or an LLM API without blocking the pipeline.

```python
class AnyDetector(Protocol):
    async def detect(self, text: str) -> list[Detection]: ...
```

`detect` returns detections in any order. Overlaps and duplicates are resolved by later pipeline stages, not by the detector.

### `Detection`

Each detector returns a list of `Detection`, a frozen dataclass carrying where the match sits, what it matched, its label, and its confidence.

| Attribute | Type | Description |
|-----------|------|-------------|
| `span` | `Span` | Where the detection sits, as a half-open range |
| `text` | `str` | The matched substring |
| `label` | `str` | The PII category, for example `PERSON` or `EMAIL` |
| `confidence` | `float` | Detector confidence, in the closed range 0 to 1 |

---

## `RegexDetector`

Finds PII by matching one regex pattern per label. Each pattern is compiled once at construction. `detect` emits one detection per non-overlapping match at a flat confidence of 1.0.

It carries no checksum validator, so it matches on shape alone. A structured value mangled by OCR is kept rather than dropped, because dropping a real value would leak it.

### Constructor

```python
RegexDetector(patterns: dict[str, str])
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `patterns` | `dict[str, str]` | Mapping of PII label to the regex pattern string to match (required) |

```python
from piighost.components.detector import RegexDetector

detector = RegexDetector({"EMAIL": r"[\w.+-]+@[\w.-]+\.\w{2,}"})
detections = await detector.detect("write to alice@example.com")
# [Detection(span=Span(9, 26), text="alice@example.com", label="EMAIL", confidence=1.0)]
```

---

## `CompositeDetector`

Runs several detectors over the same text and merges their detections. It is itself an `AnyDetector`, so it composes with the pipeline unchanged. It runs every child concurrently and concatenates their results in child order. It does not deduplicate. Overlaps and duplicates flow to the span-conflict stage.

### Constructor

```python
CompositeDetector(detectors: list[AnyDetector])
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `detectors` | `list[AnyDetector]` | The child detectors to run, in order (required) |

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

Finds occurrences of configured literal values. It scans the text for each value and emits one detection per occurrence at confidence 1.0. It carries no model and no optional dependency, which makes it the detector of choice for exercising the pipeline in tests.

### Constructor

```python
ExactMatchDetector(values: dict[str, str])
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `values` | `dict[str, str]` | Mapping of literal value to the PII label to emit for it (required) |

```python
from piighost.components.detector import ExactMatchDetector

detector = ExactMatchDetector({"Patrick": "PERSON", "Lyon": "LOCATION"})
detections = await detector.detect("Patrick lives in Lyon")
```

---

## `ChunkedDetector`

Runs a wrapped detector over each chunk of a long text. It is a decorator and itself an `AnyDetector`. It splits the text into overlapping chunks, runs the wrapped detector on each, and remaps every detection back to the original text. Strictly identical detections produced by the overlap are dropped. Label conflicts and differing confidences flow to the span-conflict stage.

### Constructor

```python
ChunkedDetector(detector: AnyDetector, splitter: AnySplitter | None = None)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `detector` | `AnyDetector` | The detector run on each chunk (required) |
| `splitter` | `AnySplitter \| None` | The splitter, or `None` for a default `RecursiveCharacterTextSplitter` |

```python
from piighost.components.detector import ChunkedDetector
from piighost.components.detector.ner import SpacyDetector

detector = ChunkedDetector(SpacyDetector(model="en_core_web_sm"))
```

---

## `LLMDetector`

Detects PII with a LangChain chat model via structured output. Needs the `llm` extra plus a provider package. The model is asked to extract `(text, label)` pairs against a schema whose label field is constrained to the configured labels. Each extracted value is then located in the source text by word-boundary search, so a value the model invented but absent from the text yields nothing. `labels` is required, since the schema is built from it.

### Constructor

```python
LLMDetector(
    model: BaseChatModel | str,
    labels: list[str] | dict[str, str],
    prompt: str | None = None,
    provider: str | None = None,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | `BaseChatModel \| str` | A loaded chat model, or a name loaded with `init_chat_model` (required) |
| `labels` | `list[str] \| dict[str, str]` | The labels to extract, list or `{emitted: internal}` map (required) |
| `prompt` | `str \| None` | A custom system prompt, or `None` for the default |
| `provider` | `str \| None` | The provider passed to `init_chat_model` when `model` is a name |

A custom `prompt` must contain a `{labels}` placeholder and, per LangChain's f-string format, double any other literal curly brace as `{{` or `}}`.

```python
from piighost.components.detector import LLMDetector

detector = LLMDetector(
    model="gpt-4o-mini",
    labels=["PERSON", "EMAIL"],
    provider="openai",
)
```

---

## NER detectors

The three model-backed detectors extend `BaseNERDetector`, which handles label mapping and filtering (see below). Each needs its own extra and takes a loaded model or a model name to load.

### `Gliner2Detector`

A zero-shot GLiNER2 model. Needs the `gliner2` extra. `labels` is required, because GLiNER2 is queried with the internal labels. A `str` model is loaded with `GLiNER2.from_pretrained`.

```python
Gliner2Detector(
    model: GLiNER2 | str,
    labels: list[str] | dict[str, str],
    threshold: float = 0.5,
    max_concurrency: int | None = None,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | `GLiNER2 \| str` | A loaded model, or a name loaded with `from_pretrained` (required) |
| `labels` | `list[str] \| dict[str, str]` | The labels to query, list or `{emitted: internal}` map (required) |
| `threshold` | `float` | The confidence at or above which an entity is kept |
| `max_concurrency` | `int \| None` | Cap on concurrent inferences, or `None` for unbounded |

### `SpacyDetector`

A spaCy NER model. Needs the `spacy` extra. `labels` is optional. When omitted, every entity spaCy produces is kept with its spaCy label. A `str` model is loaded with `spacy.load`.

```python
SpacyDetector(
    model: Language | str,
    labels: list[str] | dict[str, str] | None = None,
    max_concurrency: int | None = None,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | `Language \| str` | A loaded model, or a name loaded with `spacy.load` (required) |
| `labels` | `list[str] \| dict[str, str] \| None` | The labels to map and filter, or `None` to keep every native label |
| `max_concurrency` | `int \| None` | Cap on concurrent inferences, or `None` for unbounded |

### `TransformersDetector`

A Hugging Face token-classification pipeline. Needs the `transformers` extra. `labels` is optional, kept native when omitted. A `str` pipeline is loaded as an `ner` pipeline. An entity scoring below `threshold` is dropped.

```python
TransformersDetector(
    pipeline: TokenClassificationPipeline | str,
    labels: list[str] | dict[str, str] | None = None,
    threshold: float = 0.0,
    max_concurrency: int | None = None,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `pipeline` | `TokenClassificationPipeline \| str` | A built pipeline, or a model name loaded as an `ner` pipeline (required) |
| `labels` | `list[str] \| dict[str, str] \| None` | The labels to map and filter, or `None` to keep every native label |
| `threshold` | `float` | The score below which a detected entity is dropped |
| `max_concurrency` | `int \| None` | Cap on concurrent inferences, or `None` for unbounded |

### Label mapping

`BaseNERDetector` normalizes the `labels` argument into an external-to-internal map, then maps and filters the detections the model produces. It distinguishes the label a model uses natively from the label emitted in `Detection.label`.

- A list, `["PERSON", "LOCATION"]`, maps each label to itself.
- A map, `{"PER": "PERSON"}`, keeps only detections whose native label is a key and relabels each to its value. A native label absent from the map is dropped.
- `None` or an empty map applies no mapping, so every detection is kept with the label the model gave it.

Two external labels mapping to one internal label raise `LabelMappingError`, since the reverse lookup would be ambiguous.

```python
from piighost.components.detector.ner import TransformersDetector

detector = TransformersDetector(
    pipeline="dslim/bert-base-NER",
    labels={"PER": "PERSON", "LOC": "LOCATION"},
)
```

---

## Pattern catalogs

Reusable regex pattern sets for `RegexDetector`. Each catalog is a plain `dict[str, str]` mapping a PII label to a regex pattern string. Patterns match on shape alone, with no checksum validation.

```python
from piighost.components.detector.patterns import (
    EU_PATTERNS,
    FR_PATTERNS,
    GENERIC_PATTERNS,
    US_PATTERNS,
)
```

Feed a catalog to a `RegexDetector`, or merge several by dict merge, an inline pattern on the same label taking precedence.

```python
from piighost.components.detector import RegexDetector
from piighost.components.detector.patterns import FR_PATTERNS, GENERIC_PATTERNS

detector = RegexDetector({**GENERIC_PATTERNS, **FR_PATTERNS})
```

<div class="wide-table" markdown="1">

| Catalog | Import | Labels |
|---------|--------|--------|
| Generic | `GENERIC_PATTERNS` | `EMAIL`, `URL`, `IPV4`, `CREDIT_CARD` |
| US | `US_PATTERNS` | `US_SSN`, `US_PHONE`, `US_ZIP` |
| EU | `EU_PATTERNS` | `IBAN` |
| French | `FR_PATTERNS` | `FR_PHONE`, `FR_IBAN`, `FR_NIR`, `FR_SIRET` |

</div>

The `GENERIC_PATTERNS` labels are country-agnostic. The others are prefixed (`US_`, `FR_`) so they do not collide when catalogs are merged. `EU_PATTERNS` carries the ISO 13616 IBAN shared across member states. For country-specific numbers, use a per-country catalog.

### Pulling catalogs from a config

A regex detector config pulls catalogs by name via `catalogs`, among `generic`, `us`, `eu`, `fr`. The named catalogs merge first, then any inline `patterns`, so an inline pattern overrides a catalog pattern on the same label. A regex detector config needs at least one inline pattern or one catalog.

```toml
[detector]
type = "regex"
catalogs = ["generic", "fr"]

[detector.patterns]
INTERNAL_ID = "EMP-\\d{6}"
```

---

## See also

- [Pipeline reference](pipeline.md) for the pipeline that drives the detector.
- [Pre-built detectors](../examples/detectors.md) for composing catalogs in practice.
- [TOML configuration](../configuration/toml.md) for the declarative build.
- [Extending PIIGhost](../extending.md) for writing your own detector.
