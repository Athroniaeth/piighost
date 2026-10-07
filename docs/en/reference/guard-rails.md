---
icon: lucide/shield-check
tags:
  - Guard
---

# Guard rails reference

Module: `piighost.components.guard`

A guard rail is the pipeline's last, optional stage. It re-checks the de-identified text for residual confidential values. When it finds any, the pipeline raises `PIIRemainingError` instead of returning a leak. Every guard satisfies the `AnyGuardRail` port, an `async def check(self, text: str) -> GuardVerdict`. It returns a `GuardVerdict` carrying whether confidential values seem to remain and how it knows. Unlike the other stages, guards share no `Base*` template, because their checking mechanisms have no shared skeleton. One re-runs a local detector, another calls an external API.

The guard classifies, it does not decide. It reports a verdict. The pipeline turns a flagged verdict into an exception, and your code chooses how to react.

```python
from piighost.components.guard import (
    DetectorGuardRail,
    LLMGuardRail,
    ModerationGuardRail,
)
```

## Wire a guard into a pipeline

`AnonymizationPipeline` takes an optional `guard` argument, disabled by default. When set, the guard runs on the rendered output after de-identification, and the pipeline raises `PIIRemainingError` if the guard flags anything unexpected.

```python
--8<-- "snippets/reference_guard.py"
```

The runnable version is [`examples/guard_rail.py`](https://github.com/Athroniaeth/piighost/blob/master/examples/guard_rail.py). This script also uses a guard standalone. It calls `await guard.check(text)` and reads the verdict without raising. The local-model version is [`examples/guard_rail_local_model.py`](https://github.com/Athroniaeth/piighost/blob/master/examples/guard_rail_local_model.py).

## `DetectorGuardRail`

Re-runs a detector on the de-identified output and flags whatever it still finds, carrying the residual detections on the verdict.

```python
DetectorGuardRail(
    detector: AnyDetector,
    recognizer: BaseDelimitedPlaceholderFactory | None = None,
    ignore_placeholders: bool = True,
)
```

This guard only adds value with a detector different from the pipeline's. Re-running the same one finds nothing, since the pipeline already de-identified everything it detects. A stronger or complementary detector, run as a cheap second pass over the short de-identified output, catches what the primary detector missed. `DetectorGuardRail` needs no optional extra.

### Placeholders are ignored

A model-based detector often tags the placeholders themselves. GLiNER2 reads `<<PERSON:1>>`{ .placeholder } as a person in 169 of 200 de-identified texts, so a guard that flags on every detection refuses every text. `DetectorGuardRail` therefore drops each detection that holds only placeholders, that is, fewer than two letters or digits once its placeholders are set aside.

- `<<PERSON:1>>, <<PERSON:2>>` is dropped, nothing is left but a comma
- `<<PERSON:1>> Dubois` flags, `Dubois`{ .pii } is left
- `Mme Dubois`{ .pii } next to `<<PERSON:2>>`{ .placeholder } flags, the detection holds no placeholder

The verdict carries only the detections that flag. The guard finds placeholders with the grammar of the pipeline it runs in, custom delimiters included. Used alone, it reads the default `<<PERSON>>`, `<<PERSON:1>>` and `<<PERSON:a1b2c3d4>>` forms, or the grammar of the factory passed as `recognizer`. Pass `ignore_placeholders=False` to flag on every detection.

### A local model as the guard

The complementary detector is often a model, because the shapes a regex is good at are exactly the ones the primary pass already caught. A name, an address or a company name is what slips through:

```python
--8<-- "snippets/reference_guard_gliner2.py:example"
```

This guard localizes what leaked. That is what a detector-backed guard gives you over a classifier. For a text-level verdict from the same checkpoint, without spans and in one forward pass, see [`Gliner2GuardRail`](#gliner2guardrail).

### What it catches

The [decision guard benchmark](https://github.com/Athroniaeth/piighost/tree/master/benchmarks/decision_guard) runs this guard, with the detector above, on 200 de-identified texts. Half are French, half English, and half of them leak one value.

| Threshold | Leaks caught | False alarms |
|---|---|---|
| 0.5 | 97/100 | 49/100 |
| 0.9 | 83/100 | 3/100 |
| Chosen on the other templates | 83/100 | 7/100 |

The 0.9 threshold was chosen on the benchmark data, so its 3 false alarms are optimistic. The last row is the honest figure. For each of the 28 templates, the threshold that catches the most leaks with at most 5 % false alarms on the other 27 is tested on the one left out. Without the placeholder filter, the same detector flags all 200 texts at 0.5.

Two kinds of false alarm remain:

- a role word read as a person, such as "Customer", "[User]" or "Tenant"
- a civility next to a placeholder, such as `Mr <<PERSON:3>>`

Choose the threshold on your own documents. A threshold chosen on the French texts does not carry over exactly to the English ones.

## `LLMGuardRail`

Wraps an `LLMDetector` configured with a guard prompt that tells the model to ignore placeholders and flag only residual clear-form PII, then reports a verdict.

```python
LLMGuardRail(
    model: BaseChatModel | str,
    labels: list[str] | dict[str, str],
    prompt: str | None = None,
    provider: str | None = None,
    prefix: str = "<<",
    suffix: str = ">>",
    fail_open: bool = False,
)
```

A `str` model is loaded like `LLMDetector`'s. A loaded instance is used as-is. A custom `prompt` must contain a `{labels}` placeholder. When no custom prompt is given, `prefix` and `suffix` (default `<<` and `>>`) shape the default prompt's placeholder examples to match the delimiters the pipeline emits. An output the guard cannot read raises `UnreadableOutputError` rather than report the text clean, unless `fail_open=True`. This behavior is the same as for `LLMDetector`. Requires `piighost[llm]`.

## `Gliner2GuardRail`

Classifies the de-identified output with a GLiNER2 guardrail model running in the process, and flags the verdict when it comes back unsafe with enough confidence.

```python
Gliner2GuardRail(
    model: GLiNER2 | str = "fastino/GLiNER2-Guardrails-PII-Multi",
    task: str = "response_safety",
    labels: tuple[str, ...] = ("safe", "unsafe"),
    threshold: float = 0.5,
)
```

This is `ModerationGuardRail` without the API call, and that difference is the point. The text a guard checks is the text that still holds whatever leaked. Sending it to a third party is therefore an odd shape for the last stage of a de-identification pipeline. The default checkpoint is 300M parameters, multilingual over seven languages, and does safety moderation and PII extraction in one forward pass.

A `str` model is loaded with `GLiNER2.from_pretrained`, and a loaded instance is used as-is. That is how one checkpoint is shared between this guard and a `Gliner2Detector`. The `labels` pair is read positionally, and the refused answer comes last. Another task of the same model is therefore read the same way. For example, `task="response_refusal"` with `labels=("compliance", "refusal")` flags a refusal instead. Requires `piighost[gliner2]`.

```python
--8<-- "snippets/reference_gliner2_guard.py"
```

`Gliner2GuardRail` gives a text-level verdict, so it localizes nothing. `detections` is empty and only `score` is set. Pair it with a `DetectorGuardRail` when you need to know which value leaked. The placeholders the pipeline emits do not trip it. For example, `<<EMAIL:1>>` scores safe at 0.989. The runnable version is [`examples/guard_rail_local_model.py`](https://github.com/Athroniaeth/piighost/blob/master/examples/guard_rail_local_model.py).

## `ModerationGuardRail`

Classifies residual PII with Mistral's moderation model, reading the PII category score and flagging the verdict when it reaches the threshold.

```python
ModerationGuardRail(
    client: Mistral,
    model: str = "mistral-moderation-latest",
    threshold: float = 0.5,
)
```

This guard classifies the text, it does not detect values. It therefore catches PII a detection-based pipeline cannot localize. In return, it gives a text-level verdict without spans. Requires `piighost[mistral]`.

## `GuardVerdict` and `PIIRemainingError`

`check` returns a frozen `GuardVerdict(flagged: bool, score: float | None, detections: tuple[Detection, ...])`. The detail depends on the guard. It is a score from a moderation model, or the residual detections from a detector. Both are optional.

When a guard flags confidential values, the pipeline raises `PIIRemainingError` (a subclass of `GuardError`, itself a `PIIGhostError`). Its message names the leaked labels or the score. Its `detections` attribute holds the residual detections. It stays empty for a score-based guard, which localizes nothing.

## Configure a guard from a file

A `[guard]` section adds the stage, and its `type` field picks the guard.

```toml
[guard]
type = "detector"

[guard.detector]
type = "regex"
catalogs = ["catalog:piighost/generic", "catalog:piighost/us"]
```

| `type` | Fields | Extra |
|--------|--------|-------|
| `detector` | `[guard.detector]` (a detector config), `ignore_placeholders` (default `true`) | | 
| `gliner2` | `model` (default `fastino/GLiNER2-Guardrails-PII-Multi`), `task`, `labels`, `threshold` | `gliner2` |
| `llm` | `model`, `labels`, `prompt` (optional), `provider` (optional) | `llm` |
| `moderation` | `model` (default `mistral-moderation-latest`), `threshold` (default `0.5`) | `mistral` |

The moderation guard reads `MISTRAL_API_KEY` from the environment at build time. It raises `ConfigError` if the variable is unset. Every `[guard]` key is in the [configuration reference](../configuration/toml.md).

## See also

- [Pipeline](pipeline.md): where the guard stage sits in the run.
- [Detectors](detectors.md): the detectors a `DetectorGuardRail` re-runs.
- [Security](../security.md): what a guard does and does not protect against.
