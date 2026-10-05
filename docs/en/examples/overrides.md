---
icon: lucide/gavel
tags:
  - Advanced
  - Detector
---

# Deny and allow lists

Your detector reads your company name as a person and you want that name left alone. Your internal codenames go undetected and you want them replaced every time. Both are decisions about the detection set rather than about the detector. `DetectionOverride` is the stage that imposes them, with two detectors. The deny list (`deny_list`) holds what is always masked, and its detector's hits are forced into the set. The allow list (`allow_list`) holds what is always left in clear, and its detector's hits are dropped from the set.

The stage runs right after detection, before overlap resolution and linking. Its two lists therefore trump the detector's reading, and also a corrected set coming back from a human review. See [Architecture](../architecture.md) for the full stage order.

!!! note "Prerequisites"
    `piighost` alone, `pip install piighost`. Every example below runs as is, with no model download. Section 2 and the config file pull the generic group of the [piighost catalog](https://catalog.piighost.dev), fetched every time the pipeline is built, which needs network access. The last section reads a config file, which needs the config extra, `pip install "piighost[config]"`.

!!! note "Renamed in 2.0"
    The deny list was called the whitelist before `piighost` 2.0, and the allow list the blacklist. A config that still uses the old names is refused at load time, see [Upgrading to 2.0](../community/upgrading.md#the-override-lists-are-renamed).

## 1. Keep a value in clear with an allow list

Point a detector at the value, hand it to `DetectionOverride` as the allow list, and pass the override to the pipeline. What the allow list finds leaves the detection set, so the value reaches the model in clear.

```python
--8<-- "snippets/overrides_allow_list.py"
```

The output should be:

```text
--8<-- "snippets/overrides_allow_list.out"
```

`allow_list_strategy` decides which detections an allow list hit takes down.

- Keep `AllowListStrategy.VALUE`, the default, when the value must never be de-identified whatever the detector calls it. It clears every detection carrying the same text, whatever its case, position and label. The label you write beside the value therefore never has to match the one the primary detector emits.
- Use `AllowListStrategy.EXACT` when the label is the point, and both detectors read the value the same way. It clears a detection only when its span and its label both match the hit.
- Use `AllowListStrategy.OVERLAP` when a longer detection containing the value must go down too. It clears any detection whose span touches a span on the allow list, labels ignored.

The three modes on one text, with a detector that mislabels `Acme`{ .pii } as a person and reads `Globex Ltd`{ .pii } as one organization.

```python
--8<-- "snippets/overrides_allow_list_strategies.py"
```

The output should be:

```text
--8<-- "snippets/overrides_allow_list_strategies.out"
```

`EXACT` matched neither detection, for two reasons. The allow list says `Acme`{ .pii } is an organization, where the detector says a person. And the detector's span covers `Globex Ltd`{ .pii }, where the allow list covers `Globex`{ .pii } alone. `VALUE` compares whole values, so it cleared `Acme`{ .pii } and left `Globex Ltd`{ .pii }, whose text is not the one on the allow list. `OVERLAP` cleared both, because the span on the allow list sits inside the longer detection.

!!! note "A value on the allow list does not trip the guard rail"
    A [guard rail](../reference/guard-rails.md) re-reads the output and refuses residual confidential data. The pipeline hands it the values the allow list matched in the text, so a value you deliberately left in clear is exempt. Any other leak still raises `PIIRemainingError`.

## 2. Force a missed value with a deny list

Point a detector at the pattern the primary detector misses, here a codename a regex describes exactly, and hand it over as the deny list. Its hits enter the detection set whatever the primary detector saw.

```python
--8<-- "snippets/overrides_deny_list_catalog.py"
```

The output should be:

```text
--8<-- "snippets/overrides_deny_list_catalog.out"
```

A forced hit also replaces every detection it overlaps, so the deny list label wins over the primary reading. Use that to correct a label, not only to add a detection.

```python
--8<-- "snippets/overrides_deny_list_exact.py:example"
```

The output should be:

```text
--8<-- "snippets/overrides_deny_list_exact.out"
```

A forced value goes through linking and token assignment like any other detection, so the conversational pipeline stores it in memory and `deanonymize` restores it.

## 3. De-identify a value the assistant introduced

In a thread, a value the assistant wrote first stays in clear even when the deny list matches it. The model produced that value because it was useful in context, and it does not know the value is confidential. Replacing it would strip the model's world knowledge, and signal that this precise value is sensitive. `deny_list_strategy` decides who wins.

- Keep `DenyListStrategy.RESPECT_PROVENANCE`, the default, to leave an assistant-introduced value in clear. The deny list still guarantees the value is detected, and the same value introduced by the user is still tokenized.
- Use `DenyListStrategy.FORCE` to tokenize a value on the deny list whoever wrote it first.

```python
--8<-- "snippets/overrides_deny_list_provenance.py"
```

The output should be:

```text
--8<-- "snippets/overrides_deny_list_provenance.out"
```

## 4. Decide who wins when the two lists contradict

A value both lists match is a contradiction, and `conflict_strategy` names the winner.

- Keep `OverrideConflictStrategy.DENY_LIST_WINS`, the default, to de-identify the contradicted value. The allow list applies to the primary detections first, then the deny list is forced in last.
- Use `OverrideConflictStrategy.ALLOW_LIST_WINS` to keep it in clear. The deny list is forced in first, then the allow list clears the result, forced hits included.
- Use `OverrideConflictStrategy.RAISE` to refuse the contradiction. A span on the deny list overlapping one on the allow list raises `ConflictingOverrideError` before either list is applied.

```python
--8<-- "snippets/overrides_conflict.py"
```

The output should be:

```text
--8<-- "snippets/overrides_conflict.out"
```

`ALLOW_LIST_WINS` clears a forced hit according to the allow list strategy. With the default `VALUE`, a forced value is therefore cleared whatever label the deny list attached to it. Under `EXACT` the two lists have to agree on the label for the allow list to win.

## 5. Drive both lists from a config file

Both lists are detector configs, `[override.deny_list]` and `[override.allow_list]`, and the three strategies are keys of `[override]`. The file below forces the codename and keeps a public mailbox in clear.

```toml
--8<-- "snippets/overrides_config.toml"
```

`load_pipeline` parses the file and builds the pipeline, both lists included.

```python
--8<-- "snippets/overrides_config.py"
```

The output should be:

```text
--8<-- "snippets/overrides_config.out"
```

For every key and every accepted value, see the [TOML configuration](../configuration/toml.md).

## See also

- [Pre-built detectors](detectors.md) for the detectors the two lists are built on.
- [Pipeline reference](../reference/pipeline.md) for the `override` parameter and the stage order.
- [Guard rails](../reference/guard-rails.md) for the output check the allow list exempts a value from.
- [TOML configuration](../configuration/toml.md) for the `[override]` keys.
- [Impose a deny list and an allow list](../../../openwiki/en/processes/impose-a-whitelist-and-blacklist.md), for the business rules of the two lists, `BR-LIST-01` to `BR-LIST-08`.
