---
icon: lucide/puzzle
tags:
  - Advanced
  - Detector
---

# Extending PIIGhost

Every pipeline stage is a **port**: a `Protocol` you satisfy by implementing its one method. There is no base class to inherit, and nothing else in the pipeline changes. You can also subclass a `Base*` template where one exists, which supplies the shared skeleton and leaves you a single hook.

```mermaid
flowchart LR
    P[AnonymizationPipeline] -->|detector| D[AnyDetector]
    P -->|overlap_resolver| O[AnyOverlapResolver]
    P -->|expander| X[AnyDetectionExpander]
    P -->|linker| L[AnyEntityLinker]
    P -->|entity_resolver| R[AnyEntityResolver]
    P -->|anonymizer| A[AnyAnonymizer]
    P -->|guard| G[AnyGuardRail]
    A -->|factory| F[AnyPlaceholderFactory]
```

*The pipeline injects one component per port. Only the detector is required. The linker, anonymizer, and overlap resolver default to built-ins, and only the expand, entity-resolve, guard, and override stages default to disabled.*
{ .figure-caption }

The ports live in each component's `base.py`, under `piighost.components.*`. The data models they exchange live in `piighost.models`.

```python
--8<-- "snippets/extending_models.py"
```

A `Detection` is a `Span(start, end)` carrying `text`, `label`, and a `confidence` in the range 0 to 1. An `Entity` groups the detections that share a value, and derives its `label`, `text`, and `spans` from them. See the [data models reference](reference/models.md) for every field, method and validation error.

---

## A custom detector

A detector finds confidential data (personal data, secrets) in a text. Implement one method:

```python
--8<-- "snippets/ports.py:detector"
```

`detect` is async so an implementation can await a model server or an LLM API. Return detections in any order. Overlaps and repeats are resolved by later stages, not here.

???+ example "Regex handle detector"

    ```python
    --8<-- "snippets/extending.py:handle_detector"
    ```

To feed a detector from a fixed value list in tests, use the built-in `ExactMatchDetector` instead. See [Test a pipeline without models](examples/testing.md).

### For NER models, subclass `BaseNERDetector`

The model-backed detectors (`Gliner2Detector`, `SpacyDetector`, `TransformersDetector`) all extend `BaseNERDetector`. It maps the label a model emits internally to the label that appears in `Detection.label`, so you can query a model with the strings it detects best while producing clean labels downstream. Pass `labels` as a list for identity mapping, or as an `{emitted: internal}` dict to rename:

```python
--8<-- "snippets/extending_gliner2.py:example"
```

### Usage

```python
--8<-- "snippets/extending.py:use_detector"
```

---

## A custom overlap resolver

An overlap resolver reconciles detections whose spans overlap into a non-overlapping set. The port:

```python
--8<-- "snippets/ports.py:overlap_resolver"
```

Rather than implement `resolve` from scratch, subclass `BaseOverlapResolver`. It clusters the detections into overlap groups and hands each group to your `_reduce`, so you only decide which detections to keep from a group that overlaps.

???+ example "Longest span wins"

    ```python
    --8<-- "snippets/extending.py:longest_resolver"
    ```

The built-in `ConfidenceOverlapResolver` keeps the highest-confidence detection instead. The overlap resolver is always on. Omit it and the pipeline installs a `ConfidenceOverlapResolver`. Pass your own to change the rule. There is no supported way to disable it, since render assumes disjoint spans and raises `OverlappingSpansError` otherwise.

---

## A custom expander

An expander finds occurrences a detector missed, such as a repeat of a name flagged elsewhere. The port:

```python
--8<-- "snippets/ports.py:expander"
```

Subclass `BaseDetectionExpander`. It keeps the original detections and, for each one, adds a detection at every extra occurrence your `_find_occurrences` returns, carrying the source detection's label and confidence. An occurrence that overlaps a detection already kept is skipped, since the expander runs after the overlap resolver and the renderer refuses overlapping spans. Values are searched longest first, so a full name claims a place before its first name does.

???+ example "Whole-word repeats"

    ```python
    --8<-- "snippets/extending.py:whole_word_expander"
    ```

The built-in `WordBoundaryExpander` does exactly this. The stage is optional.

---

## A custom entity linker

A linker groups the detections that refer to the same value into entities, so every occurrence shares one placeholder. The port:

```python
--8<-- "snippets/ports.py:linker"
```

Subclass `BaseEntityLinker`. It groups detections by a key you compute in `_key`, one entity per distinct key, keeping first-occurrence order.

???+ example "Group by exact value and label"

    ```python
    --8<-- "snippets/extending.py:case_sensitive_linker"
    ```

The built-in `ExactEntityLinker` groups on the value key, the same words whatever their spaces and case, so `Patrick`{ .pii } and `patrick`{ .pii } become one entity. Use `piighost.text.value_key` in your own linker to follow the same rule, see [Unicode spaces](reference/detectors.md#unicode-spaces).

---

## A custom entity resolver

An entity resolver reconciles entities that should not coexist, such as two entities sharing a detection. The port:

```python
--8<-- "snippets/ports.py:entity_resolver"
```

Subclass `BaseEntityResolver`. It clusters entities that share a detection into groups and hands each group to your `_reduce`, which returns a consistent set, whether by merging the group into one entity or by keeping them apart. The built-ins:

- `MergeEntityResolver` merges entities that share a detection, by union-find.
- `SeparateEntityResolver` keeps them apart, giving each shared detection to one entity.
- `FuzzyEntityResolver` merges entities with similar values (needs the `fuzzy` extra).

The stage is optional.

---

## A custom placeholder factory

A placeholder factory turns entities into their replacement tokens. It is generic on a **preservation tag**, a phantom type stating what its tokens preserve, which the type checker uses to gate a consumer like the middleware. The port:

```python
--8<-- "snippets/ports.py:placeholder_factory"
```

A token is an instance of the tag, which is a `str` subclass, so it is a real string that carries its preservation level in its own type. `create` must be deterministic, the same entities yield the same tokens on every call, because the pipeline calls it more than once per run.

???+ example "Bracket label factory"

    ```python
    --8<-- "snippets/extending.py:bracket_factory"
    ```

`PreservesLabel` says the token reveals the type but not a unique identity, so this factory suits one-shot redaction, not the middleware. For a token the middleware can restore and find again, tag it `PreservesRecognizableIdentity` (or a sub-tag such as `PreservesLabeledIdentityOpaque`) and use a delimited grammar like `<<PERSON:1>>`{ .placeholder }. To wrap an inner form in delimiters without writing the wrapping yourself, subclass `BaseDelimitedPlaceholderFactory`. See [Placeholder factories](placeholder-factories.md) for the full tag taxonomy and worked examples.

### Usage

```python
--8<-- "snippets/extending.py:use_factory"
```

---

## A custom guard rail

A guard rail re-checks the de-identified output for residual confidential data. It classifies, it does not decide. It returns a `GuardVerdict` and leaves the pipeline to raise `PIIRemainingError` when a verdict is flagged. There is no `Base` template, guards differ by their whole checking mechanism. The port:

```python
--8<-- "snippets/ports.py:guard"
```

`check` sees only the de-identified text. The placeholders it carries are clearly synthetic, so a check meant for real values does not mistake them for such.

???+ example "Flag a residual @ sign"

    ```python
    --8<-- "snippets/extending.py:at_sign_guard"
    ```

The built-in `DetectorGuardRail` re-runs a detector and reports the residual detections. The stage is optional. Pass no `guard` and the output is returned unchecked.

### Usage

```python
--8<-- "snippets/extending.py:use_guard"
```

### A decision model behind the port

A decision model answers a typed question instead of generating text, which is the shape of a guard: a yes or no on the de-identified output. [`examples/guard_rail_laya.py`](https://github.com/Athroniaeth/piighost/blob/master/examples/guard_rail_laya.py) puts [Laya](https://huggingface.co/convaiinnovations/laya), an Apache 2.0 counterpart of Jev, behind the port in a dozen lines, running locally. It asks whether personal data is left and flags the verdict above a probability.

On 24 de-identified texts, half of them leaking, it caught 11 leaks out of 12 and flagged 5 clean texts out of 12 at a 0.5 threshold, where `Gliner2GuardRail` caught 4 leaks and flagged none. Placeholders raise its score, so a text dense in tokens is the one it flags wrongly. Its English checkpoint reads French well enough, `laya-multilingual` does not.

---

## Full composition

The stages are independent, so a custom detector, factory, and guard combine freely with the built-ins:

```python
--8<-- "snippets/extending.py:assemble"
```

To unit-test a custom component deterministically, feed it through `ExactMatchDetector`. See [Test a pipeline without models](examples/testing.md).
