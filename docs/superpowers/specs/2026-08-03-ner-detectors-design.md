# NER Detectors Design

Design spec for Spec B of the detector-adapters block of the PIIGhost v2 rewrite.
Internal design document, French prose, English code identifiers.

## Context

The v2 rewrite has the detector port `AnyDetector` and the pure adapters from
Spec A (`RegexDetector`, pattern catalogs, `CompositeDetector`) plus
`ExactMatchDetector` and `ChunkedDetector`. This spec covers the second of three
detector sub-projects:

- Spec A (done) : `RegexDetector` + pattern catalogs + `CompositeDetector`.
- **Spec B (this document)** : `BaseNERDetector` + `Gliner2Detector`,
  `SpacyDetector`, `TransformersDetector`.
- Spec C (later) : `LLMDetector`.

The v1 NER adapters (`src/v1_piighost/detector/`) are the reference. Each v1
adapter re-implements the same label-mapping and filtering loop inside its
`detect`. Spec B removes that duplication by lifting the shared logic into a
Template Method base, leaving each adapter to provide only backend-specific
extraction.

## Goal

Ship a `BaseNERDetector` Template Method and three thin model-backed adapters,
each behind its optional extra, with the shared label-mapping logic unit-tested
without loading any model and the adapters covered by integration tests.

## Key decision: model or name in the constructor

Each adapter accepts `model: <BackendType> | str`. Passing a loaded model
instance injects it directly (used by tests and shared workers). Passing a `str`
makes the adapter load the model itself, with the backend's own loader
(`GLiNER2.from_pretrained(name)`, `spacy.load(name)`,
`pipeline("ner", model=name)`). Loading happens once in `__init__`, synchronously,
as v1's `from_config` did.

This removes the need for a separate `from_config` classmethod in Spec B. The
later config block simply forwards a model-name string to the constructor, so no
model-loading logic is duplicated between the adapter and the config layer. Tests
inject a fake model object (never a `str`) to skip loading entirely.

## Architecture

Ports and adapters. The port `AnyDetector` is unchanged. A new abstract base
`BaseNERDetector` holds the shared Template Method; the three adapters subclass
it and implement one abstract hook.

Package layout: a new sub-package `src/piighost/components/detector/ner/` groups
the family.

- `ner/base.py` : `BaseNERDetector`, no optional import.
- `ner/gliner2.py` : `Gliner2Detector`, behind the `gliner2` extra.
- `ner/spacy.py` : `SpacyDetector`, behind the `spacy` extra.
- `ner/transformers.py` : `TransformersDetector`, behind the `transformers` extra.
- `ner/__init__.py` : eagerly exports `BaseNERDetector`; exposes the three
  adapters via a lazy `__getattr__`.

## BaseNERDetector (Template Method)

`BaseNERDetector(ABC)` provides a concrete `async def detect(self, text: str) ->
list[Detection]` (the template) and one abstract hook.

Construction: `__init__(self, labels, max_concurrency=None)` where `labels` is
`list[str] | dict[str, str] | None`.

- `_normalize(labels)` turns the argument into an `{external: internal}` dict.
  `None` or `[]` becomes `{}` (empty, meaning no mapping). A list `[a, b]`
  becomes the identity map `{a: a, b: b}`. A dict is taken as-is.
- `_build_reverse(label_map)` builds the `{internal: external}` reverse lookup.
  If two external labels map to the same internal label the reverse lookup is
  ambiguous, so it raises `LabelMappingError`.
- The optional `max_concurrency` builds an `asyncio.Semaphore` used by
  `_run_blocking`.

Properties: `internal_labels` (the mapping values, what the model is queried
with or filtered on), `external_labels` (the mapping keys). Helper `_map_label(
internal) -> str | None` returns the external label for an internal one, or
`None` when unmapped.

The template `detect`:

1. `raw = await self._raw_detect(text)` returns `list[Detection]` whose `label`
   is the model-native label, with span and confidence already built.
2. For each raw detection, resolve the label:
   - if the label map is empty, keep the native label unchanged;
   - otherwise `_map_label(native)`; if `None`, drop the detection; else
     relabel it with `dataclasses.replace(detection, label=external)`.
3. Return the resolved detections, in the order `_raw_detect` produced them.

The abstract hook: `async def _raw_detect(self, text: str) -> list[Detection]`.
Everything backend-specific lives here (model call, threshold filtering, span
field names, per-detection confidence).

Blocking inference offload: `async def _run_blocking(self, fn, *args, **kwargs)`
runs `fn` off the event loop via `asyncio.to_thread`, bounded by the optional
semaphore when `max_concurrency` was set. Adapters call the synchronous model
through it so inference does not block the asyncio loop.

## Adapters

Each adapter module is guarded: `if importlib.util.find_spec("<pkg>") is None:
raise ImportError("... install piighost[<extra>]")`, with the optional package
imported after the guard. Each implements only `_raw_detect` plus an `__init__`
that accepts `model | str`.

### Gliner2Detector (`ner/gliner2.py`, extra `gliner2`)

`__init__(self, model: GLiNER2 | str, labels: list[str] | dict[str, str],
threshold: float = 0.5, flat_ner: bool = True, max_concurrency: int | None =
None)`. A `str` model is loaded with `GLiNER2.from_pretrained(model)`. `labels`
is required, because GLiNER2 is queried with `internal_labels`.

`_raw_detect` calls, through `_run_blocking`, `model.extract_entities(text,
entity_types=self.internal_labels, threshold=self.threshold, include_spans=True,
include_confidence=True)`, then builds one `Detection` per returned entity with
the model-native label, the entity span, and the model confidence.

### SpacyDetector (`ner/spacy.py`, extra `spacy`)

`__init__(self, model: Language | str, labels: list[str] | dict[str, str] |
None = None, max_concurrency: int | None = None)`. A `str` model is loaded with
`spacy.load(model)`. `labels` is optional; `None` keeps every entity.

`_raw_detect` runs `doc = model(text)` through `_run_blocking` and builds one
`Detection` per `ent` in `doc.ents`, with label `ent.label_`, span
`Span(ent.start_char, ent.end_char)`, and confidence `1.0` (spaCy exposes no
per-entity score).

### TransformersDetector (`ner/transformers.py`, extra `transformers`)

`__init__(self, pipeline: TokenClassificationPipeline | str, labels: list[str] |
dict[str, str] | None = None, threshold: float = 0.0, max_concurrency: int |
None = None)`. A `str` pipeline is loaded with `pipeline("ner", model=<str>)`
(the Hugging Face `transformers.pipeline` factory). `labels` is optional.

`_raw_detect` runs the pipeline through `_run_blocking`, then for each returned
entity drops it when `score < threshold`, reads the native label from
`entity_group` (falling back to `entity`), and builds a `Detection` with span
`Span(start, end)`, text `text[start:end]`, and confidence `score`.

## Errors

Add to `src/piighost/exceptions.py`:

- `DetectorError(PIIGhostError)` : base for detector-construction errors.
- `LabelMappingError(DetectorError)` : raised when a label map's reverse lookup
  is ambiguous (two external labels share one internal label).

## Import safety and exports

`components/detector/__init__.py` is on the hot import path and must stay safe
without any extra, so it imports no optional adapter.

`ner/base.py` imports nothing optional, so `ner/__init__.py` eagerly imports and
exports `BaseNERDetector`. The three adapters are exposed through a lazy
`def __getattr__(name: str) -> Any` (the established v2 idiom, as in the
middleware package): accessing `Gliner2Detector`, `SpacyDetector`, or
`TransformersDetector` triggers the import then, so a missing extra fails only on
access, not on importing the package. `__all__` lists all four names.

## Testing

### Unit, no model, unmarked

The bulk of the logic is the base Template Method, tested via a fake subclass
defined in the test whose `_raw_detect` returns canned `Detection` objects (no
model, no extra). Cases:

- identity mapping from a list keeps and relabels correctly;
- an `{external: internal}` dict relabels native to external;
- with a non-empty map, a native label not in the map is dropped;
- with an empty map, every detection is kept with its native label;
- an ambiguous reverse map raises `LabelMappingError`;
- `internal_labels` and `external_labels` return the mapping values and keys;
- `_run_blocking` runs a blocking callable off the loop and returns its result.

### Conformance, unmarked

Each adapter satisfies `isinstance(detector, AnyDetector)`, constructed by
injecting a trivial fake model object (never a `str`, so no loading and no real
model). These tests require the extra to be importable.

### Integration, marked `integration`

One test per adapter loads a real model via a `str` name and runs a real
detection on a known sentence, asserting at least one expected entity with the
correct label and span. Heavy, excluded by the default test selection, run in the
`integration` lane.

### Regression

Add `("piighost.components.detector.ner", "BaseNERDetector")` to the
`PUBLIC_API` list in `tests/regression/test_imports.py`. The optional adapters
are not added there, because a `hasattr` probe would trigger their lazy import
and fail when the extra is absent; their import behavior is covered by the lazy
`__getattr__` and the existing optional-dependency conventions instead.

## Out of scope

- `from_config` and config models or builders (the config block is later; the
  `model | str` constructor already absorbs model loading).
- The `LLMDetector` (Spec C).
- Any change to the pipeline, resolvers, or the `AnyDetector` port itself.
- Chunking of NER inputs (the existing `ChunkedDetector` decorator already wraps
  any detector; wiring a default chunk size for NER is a composition-root
  concern, not part of these adapters).
