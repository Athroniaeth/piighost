---
icon: lucide/test-tube
tags:
  - Testing
---

# Test a pipeline without models

You want to assert what a pipeline produces without downloading an NER model or reaching the network. `ExactMatchDetector` gives you that: you tell it which literal values map to which label, and it finds their occurrences with a plain regex. The rest of the pipeline runs unchanged, so a test exercises real linking, resolution, and anonymization against a detector whose output you control.

Use this to test a pipeline you assembled, or a custom component you wrote, against `<<PERSON:1>>`{ .placeholder } rather than a model's guess.

## Assert one anonymized string

Build a pipeline with `ExactMatchDetector`, run it on a text, and compare `result.text` to the expected output.

```python
import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline

detector = ExactMatchDetector({"John Doe": "PERSON", "Paris": "LOCATION"})
pipeline = AnonymizationPipeline(
    detector,
    ExactEntityLinker(),
    Anonymizer(LabelCounterPlaceholderFactory()),
)


async def main() -> None:
    result = await pipeline.anonymize("John Doe lives in Paris.")
    assert result.text == "<<PERSON:1>> lives in <<LOCATION:1>>."


asyncio.run(main())
```

`ExactMatchDetector` takes a mapping of literal value to label. It emits one detection per occurrence with confidence `1.0`, so its output never varies between runs.

## Write it as a pytest test

The project runs pytest with `asyncio_mode = "auto"`, so an `async def test_...` needs no decorator. Assert both the exact output and the absence of the raw value.

```python
from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline


def build_pipeline(values: dict[str, str]) -> AnonymizationPipeline:
    return AnonymizationPipeline(
        ExactMatchDetector(values),
        ExactEntityLinker(),
        Anonymizer(LabelCounterPlaceholderFactory()),
    )


async def test_person_is_tokenized() -> None:
    """A detected person becomes its token, and the raw value is gone."""
    pipeline = build_pipeline({"Alice": "PERSON"})
    result = await pipeline.anonymize("Alice lives in Lyon.")
    assert result.text == "<<PERSON:1>> lives in Lyon."
    assert "Alice" not in result.text
```

If your own project runs pytest with the default synchronous mode, install `pytest-asyncio` and mark the test with `@pytest.mark.asyncio`, or set `asyncio_mode = "auto"` in your pytest config to drop the decorator.

## Assert that repeats share one token

Entity linking groups every occurrence of a value under one entity, so a repeated name reuses its first token. `ExactMatchDetector` finds each occurrence, `ExactEntityLinker` groups them, and the assertion checks the shared `<<PERSON:1>>`{ .placeholder }.

```python
async def test_repeat_shares_one_token() -> None:
    """A repeated value reuses its first token."""
    pipeline = build_pipeline({"Alice": "PERSON"})
    result = await pipeline.anonymize("Alice met Alice again.")
    assert result.text == "<<PERSON:1>> met <<PERSON:1>> again."
```

## Test a custom component

Every pipeline stage is a port, so you can drop your own component in beside `ExactMatchDetector` and let the deterministic detector feed it. Give the stage a fixed input through `ExactMatchDetector`, then assert on `result.text`. See [Extending PIIGhost](../extending.md) for the ports and worked component examples.
