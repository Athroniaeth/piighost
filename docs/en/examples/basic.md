---
icon: lucide/code
---

# How to de-identify a text and restore it

You have a text with PII, and you want to de-identify it, send it to an LLM, then restore the original values in the reply. This guide does the round-trip with the `piighost` core alone, no model and no optional dependency.

Install the core.

```bash
uv add piighost
```

## Do the round-trip

A pipeline chains a detector, a linker, and an anonymizer. `anonymize` returns the de-identified text and the token assigned to each entity. `deanonymize` replays that mapping in reverse.

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
    result = await pipeline.anonymize("Contact alice@example.com from 192.168.1.42.")
    print(result.text)
    # Contact <<EMAIL:1>> from <<IPV4:1>>.

    restored = pipeline.deanonymize(result.text, result.tokens)
    print(restored)
    # Contact alice@example.com from 192.168.1.42.


asyncio.run(main())
```

`result.text` carries `<<EMAIL:1>>`{ .placeholder } in place of `alice@example.com`{ .pii }. `result.tokens` maps each entity to its token. Pass it as-is to `deanonymize` to recover the original text.

## Restore an LLM reply

`deanonymize` restores any text that carries the tokens, not only the one the pipeline produced. If the LLM answers with `<<EMAIL:1>>`{ .placeholder }, put the real values back with the same `result.tokens` mapping.

```python
async def main():
    result = await pipeline.anonymize("Contact alice@example.com from 192.168.1.42.")

    llm_reply = "I sent the message to <<EMAIL:1>>."
    print(pipeline.deanonymize(llm_reply, result.tokens))
    # I sent the message to alice@example.com.


asyncio.run(main())
```

## Group repeated occurrences

A value cited several times gets a single token, so the LLM keeps the thread. `ExactEntityLinker` groups occurrences by value and label.

```python
from piighost.components.detector import ExactMatchDetector

detector = ExactMatchDetector({"Patrick": "PERSON", "Paris": "LOCATION"})
linker = ExactEntityLinker()
factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
pipeline = AnonymizationPipeline(
    detector,
    linker,
    anonymizer,
)


async def main():
    result = await pipeline.anonymize("Patrick lives in Paris. Patrick loves Paris.")
    print(result.text)
    # <<PERSON:1>> lives in <<LOCATION:1>>. <<PERSON:1>> loves <<LOCATION:1>>.


asyncio.run(main())
```

`ExactMatchDetector` detects fixed literal values, which keeps the example reproducible without loading a model. For free text, swap it for an NER or LLM detector, see the [detectors reference](../reference/detectors.md).

## Change the token shape

`LabelCounterPlaceholderFactory` produces `<<LABEL:N>>`{ .placeholder }. If you want another token shape, change the factory passed to the `Anonymizer`.

```python
from piighost.components.placeholder import (
    LabelHashPlaceholderFactory,
    LabelPlaceholderFactory,
)

# Deterministic hash, one opaque token per value: <<PERSON:a1b2c3d4>>
hash_factory = LabelHashPlaceholderFactory()
Anonymizer(hash_factory)

# Label only, no counter: <<PERSON>>
label_factory = LabelPlaceholderFactory()
Anonymizer(label_factory)
```

To restore the values, the factory must preserve identity, which `LabelCounterPlaceholderFactory` does and `LabelPlaceholderFactory` does not, since it gives the same `<<PERSON>>`{ .placeholder } to two distinct people. See the [placeholder factories](../placeholder-factories.md) page.

## See also

- [Pre-built detectors](detectors.md) to combine catalogs and detectors.
- [Pipeline reference](../reference/pipeline.md) for the optional stages.
- [Extending PIIGhost](../extending.md) to write your own components.
