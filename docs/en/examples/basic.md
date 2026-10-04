---
icon: lucide/code
---

# De-identify and restore a text

You have a text with confidential data, and you want to de-identify it, send it to an LLM, then restore the original values in the reply. This guide does the round-trip with the `piighost` core alone, no model and no optional dependency. The detector's patterns come from the [piighost hub](https://hub.piighost.dev). They are fetched every time the detector is built, which needs network access.

Install the core.

=== "uv"

    ```bash
    uv add piighost
    ```

=== "pip"

    ```bash
    pip install piighost
    ```

## Do the round-trip

A pipeline chains a detector, a linker, and an anonymizer. Only the detector is required. The linker defaults to `ExactEntityLinker` and the anonymizer to `Anonymizer(LabelCounterPlaceholderFactory())`. `anonymize` returns the de-identified text and the token assigned to each entity. `deanonymize` replays that mapping in reverse.

```python
--8<-- "snippets/basic.py:hub"
```

The output should be:

```text
--8<-- "snippets/basic.out:hub"
```

`result.text` carries `<<EMAIL:1>>`{ .placeholder } in place of `alice@example.com`{ .pii }. `result.tokens` maps each entity to its token. Pass it as-is to `deanonymize` to recover the original text.

## Restore an LLM reply

`deanonymize` restores any text that carries the tokens, not only the one the pipeline produced. If the LLM answers with `<<EMAIL:1>>`{ .placeholder }, put the real values back with the same `result.tokens` mapping.

```python
--8<-- "snippets/basic.py:reply"
```

The output should be:

```text
--8<-- "snippets/basic.out:reply"
```

## Group repeated occurrences

A value cited several times gets a single token, so the LLM keeps the thread. `ExactEntityLinker` groups occurrences by value and label.

```python
--8<-- "snippets/basic_exact.en.py:exact"
```

The output should be:

```text
--8<-- "snippets/basic_exact.en.out"
```

`ExactMatchDetector` detects fixed literal values. The example therefore stays reproducible without loading a model. For free text, swap it for an NER (named entity recognition) or LLM detector, see the [detectors reference](../reference/detectors.md).

## Change the token shape

`LabelCounterPlaceholderFactory`, the default factory, produces `<<LABEL:N>>`{ .placeholder }. If you want another token shape, pass the pipeline an `Anonymizer` built on another factory. Here, `LabelHashPlaceholderFactory` replaces the number with a short digest.

```python
--8<-- "snippets/basic_factories.py:factories"
```

The output should be:

```text
--8<-- "snippets/basic_factories.out"
```

The digest is computed from the entity's label and rank, never from the value. `Patrick`{ .pii } therefore keeps the same token at both appearances, and `Marie`{ .pii } gets another one.

To restore the values, the factory must preserve identity, that is, give each value a distinct token. `LabelCounterPlaceholderFactory` does. `LabelPlaceholderFactory` does not, because it gives the same `<<PERSON>>`{ .placeholder } to two distinct people. See the [placeholder factories](../placeholder-factories.md) page.

## See also

- [Pre-built detectors](detectors.md) to combine catalogs and detectors.
- [Pipeline reference](../reference/pipeline.md) for the optional stages.
- [Extending piighost](../extending.md) to write your own components.
