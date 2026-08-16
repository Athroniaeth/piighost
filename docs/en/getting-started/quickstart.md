---
icon: lucide/zap
---

# Quickstart

The shortest path to see `piighost` at work, without downloading a model. You will de-identify a sentence from a dictionary of known values, in under a minute.

!!! note "Prerequisites"
    `piighost` installed, see [Installation](installation.md). This example uses only the core, no extra.

```python
import asyncio

from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import AnonymizationPipeline

detector = ExactMatchDetector({"John Doe": "PERSON", "Paris": "LOCATION"})
pipeline = AnonymizationPipeline(detector)


async def main() -> None:
    result = await pipeline.anonymize("John Doe lives in Paris.")
    print(result.text)


asyncio.run(main())
```

The output should be:

```text
<<PERSON:1>> lives in <<LOCATION:1>>.
```

## How it works

`ExactMatchDetector` spots exact occurrences, at word boundaries, of the values in the dictionary you pass. Given only a detector, the pipeline fills the required stages with their defaults. It groups the detections of the same value and label with an `ExactEntityLinker`, then replaces each entity with a `LabelCounterPlaceholderFactory` that numbers per label, so `<<PERSON:1>>`{ .placeholder } and `<<LOCATION:1>>`{ .placeholder }. The optional stages, overlap resolution, entity expansion and merging, stay disabled. That is enough for a first try, with no model to load.

## What's next

- For real automatic detection, arbitrary names and locations, move on to the [First pipeline](first-pipeline.md) with an NER like GLiNER2.
- To describe a full pipeline in a file rather than in Python, see the [TOML reference](../configuration/toml.md).
- To de-identify across a conversation with persistent memory, see the [Conversational pipeline](conversation.md).
