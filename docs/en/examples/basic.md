---
icon: lucide/code
---

# How to de-identify a text and restore it

You have a text with confidential data, and you want to de-identify it, send it to an LLM, then restore the original values in the reply. This guide does the round-trip with the `piighost` core alone, no model and no optional dependency. The detector's patterns come from the [piighost hub](https://hub.piighost.dev), fetched on the first run, then read from the on-disk cache.

Install the core.

```bash
uv add piighost
```

## Do the round-trip

A pipeline chains a detector, a linker, and an anonymizer. `anonymize` returns the de-identified text and the token assigned to each entity. `deanonymize` replays that mapping in reverse.

```python
--8<-- "snippets/basic.py:hub"
```

`result.text` carries `<<EMAIL:1>>`{ .placeholder } in place of `alice@example.com`{ .pii }. `result.tokens` maps each entity to its token. Pass it as-is to `deanonymize` to recover the original text.

## Restore an LLM reply

`deanonymize` restores any text that carries the tokens, not only the one the pipeline produced. If the LLM answers with `<<EMAIL:1>>`{ .placeholder }, put the real values back with the same `result.tokens` mapping.

```python
--8<-- "snippets/basic.py:reply"
```

## Group repeated occurrences

A value cited several times gets a single token, so the LLM keeps the thread. `ExactEntityLinker` groups occurrences by value and label.

```python
--8<-- "snippets/basic_exact.en.py:exact"
```

`ExactMatchDetector` detects fixed literal values, which keeps the example reproducible without loading a model. For free text, swap it for an NER or LLM detector, see the [detectors reference](../reference/detectors.md).

## Change the token shape

`LabelCounterPlaceholderFactory` produces `<<LABEL:N>>`{ .placeholder }. If you want another token shape, change the factory passed to the `Anonymizer`.

```python
--8<-- "snippets/basic_factories.py:factories"
```

To restore the values, the factory must preserve identity, which `LabelCounterPlaceholderFactory` does and `LabelPlaceholderFactory` does not, since it gives the same `<<PERSON>>`{ .placeholder } to two distinct people. See the [placeholder factories](../placeholder-factories.md) page.

## See also

- [Pre-built detectors](detectors.md) to combine catalogs and detectors.
- [Pipeline reference](../reference/pipeline.md) for the optional stages.
- [Extending PIIGhost](../extending.md) to write your own components.
