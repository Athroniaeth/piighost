---
icon: lucide/scan-search
tags:
  - Detector
  - Regex
---

# How to use pattern catalogs and combine detectors

`piighost` ships ready-to-use regex pattern catalogs for structured PII (email, IP, IBAN, phone). This guide shows how to load them, merge them, and combine several detectors, with the `piighost` core alone.

The four catalogs are plain `label` to `pattern` dictionaries.

```python
from piighost.components.detector.patterns import (
    EU_PATTERNS,
    FR_PATTERNS,
    GENERIC_PATTERNS,
    US_PATTERNS,
)
```

- `GENERIC_PATTERNS`: email, URL, IPv4, credit card, country-agnostic.
- `US_PATTERNS`: SSN, phone, ZIP, prefixed `US_`.
- `EU_PATTERNS`: pan-European ISO 13616 IBAN.
- `FR_PATTERNS`: phone, IBAN, NIR, SIRET, prefixed `FR_`.

For the label details, see the [detectors reference](../reference/detectors.md).

## Use a single catalog

Pass the catalog to a `RegexDetector`, then assemble the pipeline.

```python
import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import RegexDetector
from piighost.components.detector.patterns import GENERIC_PATTERNS
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline

detector = RegexDetector(GENERIC_PATTERNS)
linker = ExactEntityLinker()
factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
pipeline = AnonymizationPipeline(
    detector,
    linker,
    anonymizer,
)


async def main():
    result = await pipeline.anonymize("Email alice@example.com, server 192.168.1.42.")
    print(result.text)
    # Email <<EMAIL:1>>, server <<IPV4:1>>.


asyncio.run(main())
```

## Merge generic and regional catalogs

If you want to cover both generic PII and a region's PII, merge the dictionaries. The right-hand entry wins on a shared label.

```python
from piighost.components.detector.patterns import FR_PATTERNS, GENERIC_PATTERNS

patterns = {**GENERIC_PATTERNS, **FR_PATTERNS}
detector = RegexDetector(patterns)

linker = ExactEntityLinker()
factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
pipeline = AnonymizationPipeline(
    detector,
    linker,
    anonymizer,
)


async def main():
    result = await pipeline.anonymize(
        "IBAN FR7630006000011234567890189, email marie@exemple.fr, tel 06 12 34 56 78."
    )
    print(result.text)
    # IBAN <<FR_IBAN:1>>, email <<EMAIL:1>>, tel <<FR_PHONE:1>>.


asyncio.run(main())
```

To keep only some labels, build a hand-picked dictionary.

```python
patterns = {
    "EMAIL": GENERIC_PATTERNS["EMAIL"],
    "FR_IBAN": FR_PATTERNS["FR_IBAN"],
}
detector = RegexDetector(patterns)
```

## Combine several detectors

`CompositeDetector` runs several detectors over the same text and concatenates their detections. Overlaps are arbitrated by the pipeline's resolution stage. This is how you pair a regex detector with one that recognizes names.

```python
from piighost.components.detector import CompositeDetector, ExactMatchDetector, RegexDetector
from piighost.components.detector.patterns import GENERIC_PATTERNS

exact_detector = ExactMatchDetector({"Patrick": "PERSON"})
regex_detector = RegexDetector(GENERIC_PATTERNS)
detector = CompositeDetector([exact_detector, regex_detector])

linker = ExactEntityLinker()
factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
pipeline = AnonymizationPipeline(
    detector,
    linker,
    anonymizer,
)


async def main():
    result = await pipeline.anonymize("Patrick emailed alice@example.com.")
    print(result.text)
    # <<PERSON:1>> emailed <<EMAIL:1>>.


asyncio.run(main())
```

In production, replace `ExactMatchDetector` with an NER or LLM detector, see the [detectors reference](../reference/detectors.md). `ExactMatchDetector` is used here to keep the example reproducible without a model.

## Handle a long text

An NER detector has a bounded context window, and a long document can exceed it. `ChunkedDetector` wraps any detector, splits the text into overlapping chunks, detects on each, and remaps the offsets back onto the original text.

```python
from piighost.components.detector import ChunkedDetector, RegexDetector
from piighost.components.detector.patterns import GENERIC_PATTERNS
from piighost.text import RecursiveCharacterTextSplitter

regex_detector = RegexDetector(GENERIC_PATTERNS)
splitter = RecursiveCharacterTextSplitter(chunk_size=40, chunk_overlap=10)
detector = ChunkedDetector(regex_detector, splitter=splitter)

linker = ExactEntityLinker()
factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
pipeline = AnonymizationPipeline(
    detector,
    linker,
    anonymizer,
)


async def main():
    text = (
        "Filler text here. Reach alice@example.com now. "
        "More filler padding words. Then bob@example.org later."
    )
    result = await pipeline.anonymize(text)
    print(result.text)
    # Filler text here. Reach <<EMAIL:1>> now. More filler padding words. Then <<EMAIL:2>> later.


asyncio.run(main())
```

Leave `splitter=None` for a default `RecursiveCharacterTextSplitter` tuned for real documents. The reduced `chunk_size` above only forces several chunks in a short example.

## Load catalogs from a config file

If you drive the pipeline from a config file rather than from code, a regex detector accepts a `catalogs` key.

```toml
[detector]
type = "regex"
catalogs = ["generic", "fr"]
```

Catalogs merge first, then the inline `patterns`, so an inline pattern wins on a shared label. See the [TOML configuration](../configuration/toml.md).

## See also

- [De-identify a text and restore it](basic.md) for the full round-trip.
- [Detectors reference](../reference/detectors.md) for the label catalog.
- [Extending PIIGhost](../extending.md) to write your own detectors.
