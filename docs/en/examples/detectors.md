---
icon: lucide/scan-search
tags:
  - Detector
  - Regex
---

# Pre-built detectors

`piighost` pulls ready-to-use regex pattern catalogs for structured PII (email, IP, IBAN, phone) from the [piighost hub](https://hub.piighost.dev). This guide shows how to load them, merge them, and combine several detectors, with the `piighost` core alone.

Four hub groups cover the common formats. Each one is a set of `label` to `pattern` entries.

- `hub:piighost/generic`: email, URL, IPv4, credit card, country-agnostic
- `hub:piighost/us`: phone, ZIP, ITIN, SSN, prefixed `US_`
- `hub:piighost/eu`: pan-European ISO 13616 IBAN
- `hub:piighost/fr`: phone, IBAN, NIR, SIRET, SIREN, prefixed `FR_`

A reference without a suffix follows the latest version of the group, fetched each time a detector is built. To freeze a version, add its commit after a colon, as in `hub:piighost/generic:fab51b33`. The group is then fetched once, and read from the on-disk cache afterwards, offline included. Secrets such as API keys are in the hub groups `piighost/secrets` and `piighost/secrets-extended`. These groups are pulled the same way, for example with `catalogs = ["hub:piighost/secrets"]` in a config.

For the label details, see the [detectors reference](../reference/detectors.md).

## Use a single catalog

Build a `RegexDetector` from the group with `from_hub`, then assemble the pipeline.

```python
--8<-- "snippets/detectors_hub.py"
```

The output should be:

```text
--8<-- "snippets/detectors_hub.out"
```

## Merge generic and regional catalogs

If you want to cover both generic PII and a region's PII, pull each group with `pull` and merge the dictionaries you get. `pull` returns a `label` to `pattern` dictionary. When two dictionaries share a label, the entry from the right-hand dictionary wins.

```python
--8<-- "snippets/detectors_merge.py:example"
```

The output should be:

```text
--8<-- "snippets/detectors_merge.out"
```

To keep only some labels, build a hand-picked dictionary.

```python
--8<-- "snippets/detectors_pick.py:example"
```

## Combine several detectors

`CompositeDetector` runs several detectors over the same text and concatenates their detections. Overlaps are arbitrated by the pipeline's resolution stage. This is how you pair a regex detector with one that recognizes names.

```python
--8<-- "snippets/detectors_composite.py:example"
```

The output should be:

```text
--8<-- "snippets/detectors_composite.out"
```

In production, replace `ExactMatchDetector` with an NER or LLM detector, see the [detectors reference](../reference/detectors.md). `ExactMatchDetector` is used here to keep the example reproducible without a model.

## Handle a long text

An NER detector has a bounded context window, and a long document can exceed it. `ChunkedDetector` wraps any detector, splits the text into overlapping chunks, detects on each, and remaps the offsets back onto the original text.

```python
--8<-- "snippets/detectors_chunked.py:example"
```

The output should be:

```text
--8<-- "snippets/detectors_chunked.out"
```

Leave `splitter=None` for a default `RecursiveCharacterTextSplitter` tuned for real documents. The reduced `chunk_size` above only forces several chunks in a short example.

## Load catalogs from a config file

If you drive the pipeline from a config file rather than from code, a regex detector accepts a `catalogs` key.

```toml
--8<-- "snippets/detectors_config.toml"
```

The detector merges the catalogs first, then the inline `patterns`. So on a shared label, an inline pattern wins over the one from a catalog. See the [TOML configuration](../configuration/toml.md).

## See also

- [De-identify and restore a text](basic.md) for the full round-trip.
- [Detectors reference](../reference/detectors.md) for the label catalog.
- [Extending piighost](../extending.md) to write your own detectors.
