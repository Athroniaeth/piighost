---
icon: lucide/play
---

# First pipeline

You will build a pipeline one component at a time, then run it on a sentence. You start from a detector, add the linker and the anonymizer, then put them together. The detector depends on what you look for. An NER model such as GLiNER2 detects names and locations it has never seen. A regex only recognizes fixed formats, such as an email address.

!!! note "Prerequisites"
    `piighost` installed, see [Installation](installation.md). The regex path uses only the core, no extra. The GLiNER2 path needs the `gliner2` extra and downloads a model on first load.

## 1. Pick a detector

The detector reads the text and returns detections, one per value found. The rest of the pipeline is the same whatever the detector, so pick the one that matches your text.

=== "Regex (catalog)"

    A `RegexDetector` recognizes patterns, that is strings of characters following a fixed structure. You pass it a dictionary mapping a label to a pattern. A first name has no fixed structure, so the two patterns below simply list the values of the example sentence. They show how the pipeline works, they detect no other name.

    ```python
    --8<-- "snippets/first_pipeline.en.py:detector"
    ```

    For fixed formats that do not depend on a language, such as email and URL, the [piighost hub](https://hub.piighost.dev) publishes ready-made catalogs. The `generic` group below holds no pattern for a name or a location. It is fetched from the hub every time the detector is built.

    ```python
    --8<-- "snippets/detector_hub.py:detector"
    ```

=== "GLiNER2 (NER)"

    An NER is an AI model that sorts the words of a text into categories decided in advance (name, first name, location, organization). Unlike the regex, it does not need to know the values in advance. It detects a first name it has never seen.

    ```python
    --8<-- "snippets/detector_gliner2.py:detector"
    ```

    The first argument is a model name loaded by GLiNER2, or an already loaded instance. `labels` sets the queried categories. `threshold` is the minimum confidence above which a detection is kept.

## 2. Group detections into entities

One first name can appear several times. The linker groups the detections of the same value and the same label into a single entity, so every occurrence later receives the same token.

```python
--8<-- "snippets/first_pipeline.en.py:linker"
```

## 3. Assign a token to each entity

The anonymizer replaces each entity with a placeholder, that is the token that takes its place in the text. The token depends on the chosen factory. `LabelCounterPlaceholderFactory` numbers the tokens per label. This gives `<<PERSON:1>>`{ .placeholder }, `<<PERSON:2>>`{ .placeholder }, `<<LOCATION:1>>`{ .placeholder }.

```python
--8<-- "snippets/first_pipeline.en.py:anonymizer"
```

## 4. Assemble and run

`AnonymizationPipeline` chains the three components in order. It detects, groups, then replaces. Its `anonymize` method is asynchronous. It returns a result whose `text` attribute carries the de-identified sentence.

```python
--8<-- "snippets/first_pipeline.en.py:run"
```

The output should be:

```text
--8<-- "snippets/first_pipeline.en.out"
```

Each occurrence of `Patrick`{ .pii } receives the same `<<PERSON:1>>`{ .placeholder }. `Paris`{ .pii } keeps `<<LOCATION:1>>`{ .placeholder } at both appearances. `Marie`{ .pii } receives the next number, `<<PERSON:2>>`{ .placeholder }. The linker from step 2 is what makes this consistency possible.

## How it works

`AnonymizationPipeline` runs three mandatory stages. The detector finds the confidential data. The linker groups the occurrences of the same value into one entity. The anonymizer replaces each entity with the token from its factory. Optional stages (missed-occurrence expansion, entity merging) exist, disabled by default. Overlap resolution, in contrast, runs by default. Only the detector is strictly required to construct the pipeline, and that minimum is enough for a first pipeline.

## See also

- To describe this pipeline in a file rather than in Python, see the [configuration reference](../configuration/toml.md). A regex detector takes its catalogs there with `catalogs = ["hub:piighost/generic"]`.
- To de-identify across a conversation with tokens stable between messages, see the [Conversational pipeline](conversation.md).
