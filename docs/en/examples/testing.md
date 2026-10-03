---
icon: lucide/test-tube
tags:
  - Testing
---

# Test a pipeline without models

You want to assert what a pipeline produces without downloading an NER model or reaching the network. `ExactMatchDetector` gives you that. You tell it which literal values map to which label, and it finds their occurrences with a plain regex. The rest of the pipeline runs unchanged. A test therefore exercises real linking, resolution, and de-identification against a detector whose output you control.

Use this to test a pipeline you assembled, or a custom component you wrote, against `<<PERSON:1>>`{ .placeholder } rather than a model's guess.

## Assert one de-identified string

Build a pipeline with `ExactMatchDetector`, run it on a text, and compare `result.text` to the expected output.

```python
--8<-- "snippets/testing.py"
```

`ExactMatchDetector` takes a mapping of literal value to label. It emits one detection per occurrence with confidence `1.0`, so its output never varies between runs.

## Write it as a pytest test

The project runs pytest with `asyncio_mode = "auto"`, so an `async def test_...` needs no decorator. Assert both the exact output and the absence of the raw value.

```python
--8<-- "snippets/test_testing.py:helper"
```

If your own project runs pytest with the default synchronous mode, install `pytest-asyncio` and mark the test with `@pytest.mark.asyncio`, or set `asyncio_mode = "auto"` in your pytest config to drop the decorator.

## Assert that repeats share one token

Entity linking groups every occurrence of a value under one entity, so a repeated name reuses its first token. `ExactMatchDetector` finds each occurrence, `ExactEntityLinker` groups them, and the assertion checks the shared `<<PERSON:1>>`{ .placeholder }.

```python
--8<-- "snippets/test_testing.py:repeat"
```

## Test a custom component

Every pipeline stage is a port, that is an interface any component can implement. So you can drop your own component in beside `ExactMatchDetector`, and let the deterministic detector feed it. Give the stage a fixed input through `ExactMatchDetector`, then assert on `result.text`. See [Extending PIIGhost](../extending.md) for the ports and worked component examples.
