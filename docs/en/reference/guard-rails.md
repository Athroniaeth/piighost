---
icon: lucide/shield-check
tags:
  - Guard
---

# Guard rails reference

Module: `piighost.components.guard`

A guard rail is the pipeline's last, optional stage. It re-checks the anonymized text for residual PII and, when it finds any, makes the pipeline raise `PIIRemainingError` instead of returning a leak. Every guard satisfies the `AnyGuardRail` port, an `async def check(self, text: str) -> GuardVerdict`, and returns a `GuardVerdict` carrying whether PII seems to remain and how it knows. Unlike the other stages, guards share no `Base*` template: they differ by their whole checking mechanism, re-running a local detector versus calling an external API, so there is no shared skeleton.

The guard classifies, it does not decide. It reports a verdict, and the pipeline turns a flagged verdict into an exception, leaving the choice of how to react to your code.

```python
from piighost.components.guard import (
    DetectorGuardRail,
    LLMGuardRail,
    ModerationGuardRail,
)
```

## Wire a guard into a pipeline

`AnonymizationPipeline` takes an optional `guard` argument, disabled by default. When set, the guard runs on the rendered output after anonymization, and the pipeline raises `PIIRemainingError` if the guard flags anything unexpected.

```python
from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector, RegexDetector
from piighost.components.detector.patterns import GENERIC_PATTERNS, US_PATTERNS
from piighost.components.guard import DetectorGuardRail
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.exceptions import PIIRemainingError
from piighost.pipeline import AnonymizationPipeline

# The primary detector only knows the literal name; the guard re-runs a broader
# email and phone regex over the short output to catch structured PII it missed.
guard_detector = RegexDetector({**GENERIC_PATTERNS, **US_PATTERNS})
pipeline = AnonymizationPipeline(
    ExactMatchDetector({"Emma Doe": "PERSON"}),
    ExactEntityLinker(),
    Anonymizer(LabelCounterPlaceholderFactory()),
    guard=DetectorGuardRail(guard_detector),
)

try:
    result = await pipeline.anonymize("Emma Doe, reachable at emma@acme.com.")
except PIIRemainingError as error:
    print(error)             # Anonymized text still contains PII: ['EMAIL']
    print(error.detections)  # the residual detections behind the flag
```

The runnable version is [`examples/guard_rail.py`](https://github.com/Athroniaeth/piighost/blob/master/examples/guard_rail.py), which also uses a guard standalone by calling `await guard.check(text)` and reading the verdict without raising.

## `DetectorGuardRail`

Re-runs a detector on the anonymized output and flags whatever it still finds, carrying the residual detections on the verdict.

```python
DetectorGuardRail(detector: AnyDetector)
```

This only adds value with a detector different from the pipeline's: re-running the same one finds nothing, since the pipeline already anonymized everything it detects. A stronger or complementary detector, run as a cheap second pass over the short anonymized output, catches what the primary detector missed. The synthetic placeholders are not PII-shaped, so a detector meant for real PII leaves them alone. It needs no optional extra.

## `LLMGuardRail`

Wraps an `LLMDetector` configured with a guard prompt that tells the model to ignore placeholders and flag only residual clear-form PII, then reports a verdict.

```python
LLMGuardRail(
    model: BaseChatModel | str,
    labels: list[str] | dict[str, str],
    prompt: str | None = None,
    provider: str | None = None,
)
```

A `str` model is loaded like `LLMDetector`'s; a loaded instance is used as-is. A custom `prompt` must contain a `{labels}` placeholder. Requires `piighost[llm]`.

## `ModerationGuardRail`

Classifies residual PII with Mistral's moderation model, reading the PII category score and flagging the verdict when it reaches the threshold.

```python
ModerationGuardRail(
    client: Mistral,
    model: str = "mistral-moderation-latest",
    threshold: float = 0.5,
)
```

Being a different modality from a detector, it catches PII a detection-based pipeline cannot localize, at the cost of a text-level verdict without spans. Requires `piighost[mistral]`.

## `GuardVerdict` and `PIIRemainingError`

`check` returns a frozen `GuardVerdict(flagged: bool, score: float | None, detections: tuple[Detection, ...])`. The detail depends on the guard: a score from a moderation model, or the residual detections from a detector. Both are optional.

When a guard flags PII, the pipeline raises `PIIRemainingError` (a subclass of `GuardError`, itself a `PIIGhostError`). Its message names the leaked labels or the score, and its `detections` attribute holds the residual detections, empty for a score-based guard that localizes nothing.

## Configure a guard from a file

A `[guard]` section adds the stage, discriminated on `type`.

```toml
[guard]
type = "detector"

[guard.detector]
type = "regex"
catalogs = ["generic", "us"]
```

| `type` | Fields | Extra |
|--------|--------|-------|
| `detector` | `[guard.detector]` (a detector config) | | 
| `llm` | `model`, `labels`, `prompt` (optional), `provider` (optional) | `llm` |
| `moderation` | `model` (default `mistral-moderation-latest`), `threshold` (default `0.5`) | `mistral` |

The moderation guard reads `MISTRAL_API_KEY` from the environment at build time, raising `ConfigError` if it is unset. Every `[guard]` key is in the [configuration reference](../configuration/toml.md).

## See also

- [Pipeline](pipeline.md): where the guard stage sits in the run.
- [Detectors](detectors.md): the detectors a `DetectorGuardRail` re-runs.
- [Security](../security.md): what a guard does and does not protect against.
