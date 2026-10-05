---
icon: lucide/list
tags:
  - Detector
  - Regex
---

# Detectors reference

Module: `piighost.components.detector`

A detector is the detect stage of a pipeline. It reads a text and returns the confidential data it finds. Every detector satisfies the `AnyDetector` port and returns a list of `Detection`, whatever backend it wraps.

```python
from piighost.components.detector import (
    ChunkedDetector,
    CompositeDetector,
    ExactMatchDetector,
    LLMDetector,
    RegexDetector,
)
from piighost.components.detector.ner import (
    BridgeDetector,
    Gliner2Detector,
    Gliner2PiiDetector,
    PresidioDetector,
    SpacyDetector,
    TransformersDetector,
)
```

The NER detectors each need their own extra (`gliner2`, `spacy`, `transformers`, `presidio`). `LLMDetector` needs the `llm` extra plus a provider package.

---

## `AnyDetector` (protocol)

This is the port every detector implements. Its single method is async, so an implementation can await I/O such as a model server or an LLM API without blocking the pipeline.

```python
@runtime_checkable
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
| `label` | `str` | The category of the detected value, for example `PERSON` or `EMAIL` |
| `confidence` | `float` | Detector confidence, in the closed range 0 to 1 |

---

## `RegexDetector`

Finds confidential data by matching one regex pattern per label. Each pattern is compiled once at construction, under `re.ASCII`, so `\d` and the other shape classes match ASCII only. A Unicode digit look-alike such as an Arabic-Indic numeral does not match, since the formats the detector targets use ASCII digits. `detect` emits one detection per non-overlapping match at a flat confidence of 1.0. Every Unicode space in the text is read as an ordinary one, see [Unicode spaces](#unicode-spaces).

It carries no checksum validator. It therefore recognizes a value by its shape alone. A structured value mangled by OCR is kept rather than dropped, because dropping a real value would leak it.

### Constructor

```python
RegexDetector(patterns: dict[str, str])
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `patterns` | `dict[str, str]` | Mapping of label to the regex pattern string to match (required) |

```python
--8<-- "snippets/reference_detectors.py:regex"
```

### `from_catalog`

```python
RegexDetector.from_catalog(ref: str, *, catalog: str | None = None) -> RegexDetector
```

Builds a detector from the regexes a [piighost catalog](https://catalog.piighost.dev) reference carries. The catalog publishes tested de-identification regexes, addressed by `namespace/name` and an optional selector, either a tag or the eight hex characters of a commit.

| Parameter | Type | Description |
|-----------|------|-------------|
| `ref` | `str` | A reference, `namespace/name` with an optional `:selector` and an optional `catalog:` prefix. Without a selector it resolves to `latest` (required) |
| `catalog` | `str \| None` | Origin of the catalog to pull from. Defaults to `PIIGHOST_CATALOG_URL`, then to the public catalog |

```python
--8<-- "snippets/reference_regex_catalog.py:from_catalog"
```

A reference pinned to a commit is immutable, so the answer is cached under `~/.cache/piighost/catalog` and read from disk on every later call. A reference pointing at a tag or at `latest` can change, so it is fetched every time, because a stale answer would quietly detect less than the caller asked for.

The call raises a subclass of `CatalogError` (`piighost.catalog`) when the reference does not parse, the catalog cannot be reached, or the reference resolves to something other than a plain regex detector. That last case covers a reference carrying a model detector. Its regexes alone would detect less than the reference promises, so the call fails instead of returning half of it.

`from_catalog` uses the standard library only, so the core install needs no extra.

Code written for 1.x still runs. `RegexDetector.from_hub(ref, hub=...)` builds the same detector as `from_catalog`, a `hub:` prefix reads as `catalog:`, `PIIGHOST_HUB_URL` is read when `PIIGHOST_CATALOG_URL` is unset, and `piighost.hub` re-exports `piighost.catalog` under its 1.x names.


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
--8<-- "snippets/reference_composite.py"
```

---

## `ExactMatchDetector`

Finds whole-word occurrences of configured literal values. It scans the text for each value and emits one detection per occurrence at confidence 1.0. Matching is on word boundaries, so a value does not fire inside a longer word (`Ann`{ .pii } does not match inside `Anne`{ .pii }). Matching is case-insensitive by default. A value therefore matches whatever its casing, and the detection keeps the text as it appears. A space inside a value matches any run of whitespace, see [Unicode spaces](#unicode-spaces). A value made only of spaces is refused. It carries no model and no optional dependency. That makes it the detector of choice for exercising the pipeline in tests.

### Constructor

```python
ExactMatchDetector(values: dict[str, str], case_sensitive: bool = False)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `values` | `dict[str, str]` | Mapping of literal value to the label to emit for it (required) |
| `case_sensitive` | `bool` | Whether matching respects case. `False` by default |

```python
--8<-- "snippets/reference_detectors.py:exact"
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
--8<-- "snippets/reference_chunked.py"
```

---

## `LLMDetector`

Detects PII with a LangChain chat model via structured output. Needs the `llm` extra plus a provider package. The model is asked to extract `(text, label)` pairs following a schema. The label field of that schema accepts only the configured labels. Each extracted value is then located in the source text by word-boundary search, so a value the model invented but absent from the text yields nothing. `labels` is required, since the schema is built from these labels. The source text is wrapped in `<text_to_analyze>` tags. The system prompt instructs the model to treat the tagged content as data, never as instructions. A prompt-injection attempt inside the text therefore cannot steer the extraction.

### Constructor

```python
LLMDetector(
    model: BaseChatModel | str,
    labels: list[str] | dict[str, str],
    prompt: str | None = None,
    provider: str | None = None,
    confidence: float = 1.0,
    fail_open: bool = False,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | `BaseChatModel \| str` | A loaded chat model, or a name loaded with `init_chat_model` (required) |
| `labels` | `list[str] \| dict[str, str]` | The labels to extract, list or `{emitted: internal}` map (required) |
| `prompt` | `str \| None` | A custom system prompt, or `None` for the default |
| `provider` | `str \| None` | The provider passed to `init_chat_model` when `model` is a name |
| `confidence` | `float` | Confidence carried on every detection, default 1.0, so an LLM detector can be scored against a NER one at overlap resolution |
| `fail_open` | `bool` | Whether an output the detector cannot read passes as zero detections, default `False` |

A custom `prompt` must contain a `{labels}` placeholder. It must also double any other literal curly brace as `{{` or `}}`, per LangChain's f-string format.

An output the detector cannot read, a broken JSON or a result without its `entities` field, raises `UnreadableOutputError`, so a failing model refuses the message instead of sending it undetected. The error names the type of the output, never its text. With `fail_open=True` the message goes on without detection and a warning is logged, for a deployment that puts availability before protection.

```python
--8<-- "snippets/reference_llm_detector.py:example"
```

---

## NER detectors

The model-backed detectors extend `BaseNERDetector`, which handles label mapping and filtering (see below). Each needs its own extra and takes a loaded model or a model name to load, except `PresidioDetector`, which takes a constructed `AnalyzerEngine`.

### `Gliner2Detector`

A zero-shot GLiNER2 model. Needs the `gliner2` extra. `labels` is required, because GLiNER2 is queried with the internal labels. A `str` model is loaded with `GLiNER2.from_pretrained`.

```python
Gliner2Detector(
    model: GLiNER2 | str,
    labels: list[str] | dict[str, str],
    threshold: float = 0.5,
    max_concurrency: int | None = None,
    max_chars: int | None = None,
    auto_chunk: bool = True,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | `GLiNER2 \| str` | A loaded model, or a name loaded with `from_pretrained` (required) |
| `labels` | `list[str] \| dict[str, str]` | The labels to query, list or `{emitted: internal}` map (required) |
| `threshold` | `float` | The confidence at or above which an entity is kept |
| `max_concurrency` | `int \| None` | Cap on concurrent inferences, or `None` for unbounded |
| `max_chars` | `int \| None` | Character bound a single inference sees, or `None` for no bound |
| `auto_chunk` | `bool` | Whether a text longer than `max_chars` is chunked and remapped, else raises `TextTooLongError` |

### `Gliner2PiiDetector`

A ready-to-use `Gliner2Detector` over fastino's GLiNER2 model fine-tuned for PII. The model and the label map are preset, so neither a model id nor a `labels` argument is needed. The preset spans the model's taxonomy, from names and contact details to identifiers, payment data, digital identity, secrets, and sensitive dates. Pass `labels` to narrow or extend the set, or `model` to inject a loaded instance, for example in a test, so no weights are downloaded.

```python
Gliner2PiiDetector(
    model: GLiNER2 | str | None = None,
    labels: list[str] | dict[str, str] | None = None,
    threshold: float = 0.5,
    max_concurrency: int | None = None,
    max_chars: int | None = None,
    auto_chunk: bool = True,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | `GLiNER2 \| str \| None` | A loaded model or a name, or `None` for the preset PII model |
| `labels` | `list[str] \| dict[str, str] \| None` | The labels to query, or `None` for the preset PII label map |
| `threshold` | `float` | The confidence at or above which an entity is kept |
| `max_concurrency` | `int \| None` | Cap on concurrent inferences, or `None` for unbounded |
| `max_chars` | `int \| None` | Character bound a single inference sees, or `None` for no bound |
| `auto_chunk` | `bool` | Whether a text longer than `max_chars` is chunked and remapped, else raises `TextTooLongError` |

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

A Hugging Face token-classification pipeline. Needs the `transformers` extra. `labels` is optional. When omitted, every native label is kept. A `str` pipeline is loaded as an `ner` pipeline. An entity scoring below `threshold` is dropped.

```python
TransformersDetector(
    pipeline: TokenClassificationPipeline | str,
    labels: list[str] | dict[str, str] | None = None,
    threshold: float = 0.0,
    max_concurrency: int | None = None,
    aggregation_strategy: str = "simple",
    max_chars: int | None = None,
    auto_chunk: bool = True,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `pipeline` | `TokenClassificationPipeline \| str` | A built pipeline, or a model name loaded as an `ner` pipeline (required) |
| `labels` | `list[str] \| dict[str, str] \| None` | The labels to map and filter, or `None` to keep every native label |
| `threshold` | `float` | The score below which a detected entity is dropped |
| `max_concurrency` | `int \| None` | Cap on concurrent inferences, or `None` for unbounded |
| `aggregation_strategy` | `str` | How sub-word tokens are grouped into whole entities, applied only when building from a model name. An injected pipeline keeps its own. Defaults to `"simple"` |
| `max_chars` | `int \| None` | Character bound a single inference sees, or `None` for no bound |
| `auto_chunk` | `bool` | Whether a text longer than `max_chars` is chunked and remapped, else raises `TextTooLongError` |

### `PresidioDetector`

Wraps a Presidio `AnalyzerEngine` so a caller reuses Presidio's recognizers. Needs the `presidio` extra. The analyzer is injected, since an engine is assembled from an NLP engine and a recognizer registry, not loaded from a name. `labels` is optional. When omitted, every native type is kept. An entity scoring below `threshold` is dropped.

```python
PresidioDetector(
    analyzer: AnalyzerEngine,
    labels: list[str] | dict[str, str] | None = None,
    language: str = "en",
    threshold: float = 0.0,
    max_concurrency: int | None = None,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `analyzer` | `AnalyzerEngine` | A constructed Presidio analyzer (required) |
| `labels` | `list[str] \| dict[str, str] \| None` | The labels to map and filter, or `None` to keep every native type |
| `language` | `str` | The language code passed to `analyze` |
| `threshold` | `float` | The score below which a finding is dropped |
| `max_concurrency` | `int \| None` | Cap on concurrent inferences, or `None` for unbounded |

From a config, the `presidio` detector type builds Presidio's default English `AnalyzerEngine`. For another language or custom recognizers, construct the engine yourself and use `PresidioDetector` directly.

### `BridgeDetector`

Delegates inference to an injected runner and converts its answer into detections. It holds no model and needs no extra. It exists for a runtime where no NER stack is installable. The usual case is a browser. There the model runs in the host's JavaScript runtime, and Python awaits it through the Pyodide FFI. The same shape serves any out-of-process runner, a subprocess or a sidecar.

`labels` is required, since the runner is queried with the internal labels and a span whose label is not mapped is dropped, as for any NER adapter. `offset_unit` is required too, since nothing in a payload says whether its offsets count code points or UTF-16 units.

```python
BridgeDetector(
    runner: AnySpanRunner,
    labels: list[str] | dict[str, str],
    *,
    offset_unit: OffsetUnit,
    threshold: float = 0.5,
    max_chars: int | None = None,
    auto_chunk: bool = True,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `runner` | `AnySpanRunner` | The callable awaited for each text, holding the model (required) |
| `labels` | `list[str] \| dict[str, str]` | The labels to map and filter (required) |
| `offset_unit` | `OffsetUnit` | What the runner counts in its offsets, `CODE_POINT` or `UTF16` (required) |
| `threshold` | `float` | The confidence at or above which a span is kept, passed to the runner and applied again on its answer |
| `max_chars` | `int \| None` | Bound above which the text is chunked, or `None` for no bound |
| `auto_chunk` | `bool` | Whether a text over `max_chars` is chunked rather than refused |

The runner is an async callable taking the text, the internal labels and the threshold, and returning a sequence of mappings carrying `start`, `end`, `label` and `score`. Offsets are half-open positions into the text passed in, counted in the unit `offset_unit` names.

| `OffsetUnit` | Counts | Runner |
|---|---|---|
| `CODE_POINT` | characters, as a Python `str` and `Span` do | written in Python |
| `UTF16` | UTF-16 code units, where an emoji or a rare ideograph takes two | written in JavaScript, in a browser or in Node |

On a text with no emoji or rare ideograph, the two units agree. After each such character, they drift apart by one. A JavaScript offset read as a code point lands one character late, and the first letter of the value stays in clear. A JavaScript runner therefore declares `UTF16`, and the detector converts.

```python
--8<-- "snippets/reference_detectors.py:bridge"
```

A runner is foreign code, often reached across a language boundary, so its answer is checked rather than trusted.

- Any `text` the runner returns is ignored and re-read from the source, so a runner that mangles the matched substring cannot desynchronise the replacement.
- A span missing a field, or carrying an offset that is not an integer, a float such as `8.9` or `8.0` included, raises `BridgePayloadError`. Truncating such an offset would move the span.
- A span falling outside the text, or a UTF-16 offset between the two halves of a character, raises `BridgeSpanRangeError`. Trimming the span would slice a shorter substring than the runner meant, and leave part of the value in clear.
- A span scored below `threshold` is dropped, even when the runner ignored the threshold it was given.
- A result carrying a `to_py` method, as a Pyodide `JsProxy` does, is converted first.

There is no configuration model for this detector. Its runner is a callable. A TOML or JSON file cannot name a callable without a registry of callables, and that registry would make the core depend on what configures it. A caller that builds this detector builds it in code.

### Long-text handling

`Gliner2Detector`, `TransformersDetector` and `BridgeDetector` take `max_chars` with `auto_chunk` (default `True`). A text longer than `max_chars` is split into overlapping chunks, scanned separately, and remapped back onto the original text. With `auto_chunk` off, a text over the bound raises `TextTooLongError` instead. `max_chars` defaults to `None`, so there is no bound and the whole text is scanned in one pass. `SpacyDetector` and `PresidioDetector` do not expose these two parameters.

### Guarantees every NER detector keeps

`BaseNERDetector` applies one pass to whatever a model returns, so every adapter behaves alike, whatever its backend.

- The text of a detection is its span's slice of the source, never the string the model returned. Merging overlaps, linking and restoring all rely on the text matching the characters it replaces.
- A detection scored below `threshold` is dropped, even when the model was handed the threshold and let a weaker one through.
- Labels are mapped and filtered, as the next section describes.

### Label mapping

`BaseNERDetector` normalizes the `labels` argument into an external-to-internal map, then maps and filters the detections the model produces. It distinguishes the label a model uses natively from the label emitted in `Detection.label`.

- A list, `["PERSON", "LOCATION"]`, maps each label to itself.
- A map, `{"PERSON": "PER"}`, takes the emitted label as its key and the model's native label as its value. A detection the model labels `PER` is therefore emitted as `PERSON`. A native label absent from the map values is dropped.
- `None` or an empty map applies no mapping, so every detection is kept with the label the model gave it.

Two external labels mapping to one internal label raise `LabelMappingError`, since the reverse lookup would be ambiguous.

```python
--8<-- "snippets/reference_transformers.py"
```

---

## Catalog groups

Reusable regex pattern sets for `RegexDetector`, published as groups on the [piighost catalog](https://catalog.piighost.dev). Each group maps a PII label to a regex pattern string. Patterns match on shape alone, with no checksum validation.

<div class="wide-table" markdown="1">

| Group | Reference | Labels |
|-------|-----------|--------|
| Generic | `catalog:piighost/generic` | `EMAIL`, `URL`, `IPV4`, `CREDIT_CARD` |
| US | `catalog:piighost/us` | `US_PHONE`, `US_ZIP`, `US_ITIN`, `US_SSN` |
| EU | `catalog:piighost/eu` | `IBAN` |
| French | `catalog:piighost/fr` | `FR_PHONE`, `FR_IBAN`, `FR_NIR`, `FR_SIRET`, `FR_SIREN` |
| Secrets | `catalog:piighost/secrets` | `OPENAI_API_KEY`, `AWS_ACCESS_KEY`, `GITHUB_TOKEN`, `STRIPE_KEY` |

</div>

Build a detector from one group with [`from_catalog`](#from_catalog). `pull` (`piighost.catalog`) returns a group as a `dict[str, str]` in catalog order. Several groups therefore merge like dicts, and on a shared label, the right-hand entry wins.

```python
--8<-- "snippets/reference_regex_catalog.py:merge"
```

A reference pinned to a commit ends with the commit's eight hex characters, after the last colon, as in `catalog:piighost/generic:fab51b33`. It is fetched the first time a detector is built, then read from the on-disk cache, even offline. An unpinned reference, `catalog:piighost/generic` or `catalog:piighost/generic:latest`, is fetched at every build.

The catalog checks every pattern it publishes against catastrophic backtracking, so an adversarial input cannot turn a scan into a denial of service.

The generic labels are country-agnostic. The others are prefixed (`US_`, `FR_`) so they do not collide when groups are merged. The EU group carries the ISO 13616 IBAN shared across member states. For country-specific numbers, use a per-country group.

### Pulling groups from a config

A regex detector config pulls catalog groups via `catalogs`. An entry is a catalog reference written `catalog:namespace/name` with an optional `:selector`. A reference written `hub:namespace/name`, as in 1.x, is still accepted. The groups merge in order, then any inline `patterns` are added. An inline pattern therefore overrides a group pattern on the same label. A regex detector config needs at least one inline pattern or one catalog reference.

```toml
[detector]
type = "regex"
catalogs = ["catalog:piighost/generic", "catalog:piighost/fr"]

[detector.patterns]
INTERNAL_ID = "EMP-\\d{6}"
```

A catalog reference names a reviewed group instead of carrying a copy of it. The config therefore stays short, and the patterns stay auditable at their source. A group is fetched when the config is built, not when it is parsed. Set `PIIGHOST_CATALOG_URL` to pull from a private catalog.

An entry that is not a catalog reference fails at load time rather than as a bad URL later. The names `generic`, `us`, `eu` and `fr`, which named pattern sets shipped inside the library before 2.0, are refused, and the error message gives the reference that replaces them.

```text
the built-in catalog 'generic' was removed in piighost 2.0: name the catalog group instead, catalog:piighost/generic
```

## Unicode spaces

A value is often typed with a space that is not the ASCII one. Word puts a no-break space (U+00A0) or a narrow no-break space (U+202F) inside a phone number or an IBAN, PDF extraction yields thin and figure spaces, and East Asian text uses the ideographic space (U+3000). `piighost` reads every Unicode space separator (category Zs) as an ordinary space, and every line separator (U+0085, U+2028, U+2029) as a newline. This rule applies at three stages.

| Stage | Components | What it guarantees |
|---|---|---|
| Detection | `RegexDetector` | A pattern written with a space or with `\s` matches a value typed with any Unicode space. The patterns run on a copy of the text of the same length, so the offsets hold and the detected text keeps its spaces as written. |
| Search | `ExactMatchDetector`, `LLMDetector`, `WordBoundaryExpander` | A space inside a searched value matches any run of whitespace, a line break included, so `Paul Martin`{ .pii } is found again across a no-break space, two spaces or a line break. |
| Identity | `ExactEntityLinker`, overrides, conversation memory, `FuzzyEntityResolver` | Two values are the same when they have the same words, whatever the spaces between them and their case, so they share one token. |

The rule holds for every pattern, those of the catalog included, so a pattern needs no case for these characters. A pattern that looks for a no-break space on purpose no longer finds one, since the copy it runs on has ordinary spaces instead. Zero-width characters (U+200B, U+2060, U+FEFF) are not spaces and are left as they are.

The two helpers of this rule, `normalize_spaces` and `value_key`, are public in `piighost.text`, for a custom detector or linker that should follow the same rule.

```python
--8<-- "snippets/reference_text.en.py:example"
```

## Whole-word search

`ExactMatchDetector`, `LLMDetector` and `WordBoundaryExpander` find a value only where it stands as a whole word, so the character before it and the one after must not belong to a word.

| Character | Role | Example |
|---|---|---|
| letter, digit, underscore | inside a word | `Jean`{ .pii } is not found in `Jeanne`{ .pii } |
| hyphen, every Unicode one | inside a word | `Jean`{ .pii } is not found in `Jean-Paul`{ .pii }, whichever hyphen joins them |
| dash, en or em | bounds a word | `Paris`{ .pii } is found in `Paris–Lyon`{ .pii } |
| apostrophe, straight or curly | bounds a word | `Anne`{ .pii } is found in `d'Anne`{ .pii }, `Jean`{ .pii } in `Jean's`{ .pii } |
| space, every Unicode one | bounds a word | see [Unicode spaces](#unicode-spaces) |

The hyphens are the ASCII one, the hyphen and the non-breaking hyphen Word types in its place, the soft hyphen, the Hebrew maqaf, and every other dash punctuation Unicode names a hyphen. They are `WORD_JOIN_CHARS` in `piighost.text.boundaries`.

The apostrophe bounds a word in every language, since it ends a word as often as it sits inside one. The cost is that `Brien`{ .pii } is also found inside `O'Brien`{ .pii }. The mask then covers more than asked, but leaves nothing in clear.

The rule assumes spaces between words, so it finds nothing in Chinese, Japanese or Thai, see [Limitations](../limitations.md#whole-word-search-assumes-spaces-between-words).

---

## See also

- [Pipeline reference](pipeline.md) for the pipeline that drives the detector.
- [Pre-built detectors](../examples/detectors.md) for composing catalog groups in practice.
- [TOML configuration](../configuration/toml.md) for the declarative build.
- [Extending piighost](../extending.md) for writing your own detector.
- [Data models reference](models.md) for the full shape of a `Detection`.
