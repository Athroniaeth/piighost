---
icon: lucide/zap
---

# Quickstart

The shortest path to see `piighost` at work, without downloading a model. You will de-identify a sentence from a dictionary of known values, in under a minute.

!!! note "Prerequisites"
    `piighost` installed, see [Installation](installation.md). This example uses only the core, no extra.

```python
--8<-- "snippets/quickstart.en.py"
```

The output should be:

```text
--8<-- "snippets/quickstart.en.out"
```

## How it works

`ExactMatchDetector` spots the values of the dictionary at word boundaries. The pipeline fills the other stages with their defaults, including an anonymizer that numbers the tokens per label. The [First pipeline](first-pipeline.md) builds these stages one at a time.

## See also

- For real automatic detection, arbitrary names and locations, move on to the [First pipeline](first-pipeline.md) with an NER like GLiNER2.
- To describe a full pipeline in a file rather than in Python, see the [configuration reference](../configuration/toml.md).
- To de-identify across a conversation with persistent memory, see the [Conversational pipeline](conversation.md).
