---
icon: lucide/play
---

# First pipeline

You will build a pipeline that detects arbitrary names and locations, not only values known in advance, and watch it run at each step. Two detectors fit this, an NER model (GLiNER2) or a catalog of regex patterns. You start from a detector, add the three remaining components one at a time, then run the pipeline on a sentence.

!!! note "Prerequisites"
    `piighost` installed, see [Installation](installation.md). The regex path uses only the core, no extra. The GLiNER2 path needs the `gliner2` extra and downloads a model on first load.

## 1. Pick a detector

The detector reads the text and returns detections, one per PII found. The rest of the pipeline is the same whatever the detector, so pick the one that matches your text.

=== "Regex (catalog)"

    A `RegexDetector` recognizes patterns, that is strings of characters following a fixed structure. For arbitrary names and locations, you pass it a dictionary mapping a label to a pattern. Here two patterns, one for first names, one for the city.

    ```python
    from piighost.components.detector import RegexDetector

    patterns = {
        "PERSON": r"\b(?:Patrick|Marie)\b",
        "LOCATION": r"\bParis\b",
    }
    detector = RegexDetector(patterns)
    ```

    `piighost` also ships ready-made catalogs for formats that are not language-specific, such as email and URL.

    ```python
    from piighost.components.detector import RegexDetector
    from piighost.components.detector.patterns import GENERIC_PATTERNS

    detector = RegexDetector(GENERIC_PATTERNS)
    ```

=== "GLiNER2 (NER)"

    An NER is an AI model that, over a text, classifies words according to a classification decided in advance (name, first name, location, organization). Unlike the regex, it does not need to know the values in advance, it detects a first name it has never seen.

    ```python
    from piighost.components.detector.ner import Gliner2Detector

    detector = Gliner2Detector(
        model="fastino/gliner2-multi-v1",
        labels=["PERSON", "LOCATION"],
        threshold=0.5,
    )
    ```

    The first argument is a model name loaded by GLiNER2, or an already loaded instance. `labels` sets the queried categories. `threshold` is the minimum confidence above which a detection is kept.

## 2. Group detections into entities

One first name can appear several times. The linker groups the detections of the same value and the same label into a single entity, so every occurrence later receives the same token.

```python
from piighost.components.linker import ExactEntityLinker

linker = ExactEntityLinker()
```

## 3. Assign a token to each entity

The anonymizer replaces each entity with a placeholder, that is the token that takes its place in the text. The token depends on the chosen factory. `LabelCounterPlaceholderFactory` numbers per label, so `<<PERSON:1>>`{ .placeholder }, `<<PERSON:2>>`{ .placeholder }, `<<LOCATION:1>>`{ .placeholder }.

```python
from piighost.components.anonymizer import Anonymizer
from piighost.components.placeholder import LabelCounterPlaceholderFactory

factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
```

## 4. Assemble and run

`AnonymizationPipeline` chains the three components in order, detect, group, replace. Its `anonymize` call is asynchronous and returns a result whose `text` carries the de-identified sentence.

```python
import asyncio

from piighost.pipeline import AnonymizationPipeline

pipeline = AnonymizationPipeline(detector, linker, anonymizer)


async def main() -> None:
    text = "Patrick habite à Paris. Patrick aime Paris. Marie aussi."
    result = await pipeline.anonymize(text)
    print(result.text)


asyncio.run(main())
```

The output should be:

```text
<<PERSON:1>> habite à <<LOCATION:1>>. <<PERSON:1>> aime <<LOCATION:1>>. <<PERSON:2>> aussi.
```

Each occurrence of `Patrick`{ .pii } receives the same `<<PERSON:1>>`{ .placeholder }, `Paris`{ .pii } keeps `<<LOCATION:1>>`{ .placeholder } at both appearances, and `Marie`{ .pii } receives the next number `<<PERSON:2>>`{ .placeholder }. The linker from step 2 is what makes this consistency possible.

## How it works

`AnonymizationPipeline` runs three mandatory stages. The detector finds the PII, the linker groups the occurrences of the same value into one entity, the anonymizer replaces each entity with the token from its factory. Optional stages exist (missed-occurrence expansion, entity merging), disabled by default, while overlap resolution runs by default. Only the detector is strictly required to construct, which is enough for a first pipeline.

## What's next

- To describe this pipeline in a file rather than in Python, see the [TOML reference](../configuration/toml.md). A regex detector takes its catalogs there with `catalogs = ["generic"]`.
- To de-identify across a conversation with tokens stable between messages, see the [Conversational pipeline](conversation.md).
