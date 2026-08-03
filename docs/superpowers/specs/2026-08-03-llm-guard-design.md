# LLM Guard Rail Design

Design spec for the LLM guard rail of the PIIGhost v2 rewrite. Internal design
document, French prose, English code identifiers.

## Context

The v2 guard package (`src/piighost/components/guard/`) has the port
`AnyGuardRail` (`check(text: str) -> GuardVerdict`), the `GuardVerdict`
dataclass, `DetectorGuardRail` (re-runs a detector), and `ModerationGuardRail`
(Mistral, behind the `mistral` extra). The v1 `LLMGuardRail`
(`src/v1_piighost/guard_llm.py`) is not ported yet.

The `LLMDetector` from Spec C already exists at
`src/piighost/components/detector/llm.py`.

## Goal

Add `LLMGuardRail`, a guard that re-checks anonymized text with an LLM prompted
to ignore placeholders and flag only residual clear-form PII, reusing
`LLMDetector` and returning a `GuardVerdict`.

## Key decisions

- **Dedicated class over composition.** A guard could be composed as
  `DetectorGuardRail(LLMDetector(model, labels, prompt=guard_prompt))`, but a
  dedicated `LLMGuardRail` encapsulates the guard-specific prompt as a default
  and reads as a peer of `ModerationGuardRail`. The port's own docstring already
  names the LLM API as a distinct guard mechanism.
- **Returns a verdict, does not raise.** Unlike v1, which raised
  `PIIRemainingError` inside `check`, v2 conforms to the port:
  `check(text) -> GuardVerdict`. The pipeline or caller decides to raise.
- **No `tokens` parameter.** v2's port dropped it. The guard relies on its prompt
  to make the LLM ignore placeholders, not on a post-hoc token filter. A
  misbehaving LLM that flags a placeholder would produce a false positive; the
  prompt is the mitigation. This is the accepted trade-off of the token-free
  port.

## Architecture

`LLMGuardRail` lives at `src/piighost/components/guard/llm.py`, behind the `llm`
extra (`langchain-core` + `langchain`, the same extra as `LLMDetector`).

It wraps an internal `LLMDetector` configured with a guard-specific prompt:

- `__init__(self, model: BaseChatModel | str, labels: list[str] | dict[str,
  str], prompt: str | None = None, provider: str | None = None)` builds
  `self._detector = LLMDetector(model, labels, prompt=prompt or _GUARD_PROMPT,
  provider=provider)`. The signature mirrors `LLMDetector`'s, so a loaded chat
  model or a model name (plus provider) both work.
- `async def check(self, text: str) -> GuardVerdict`: `residual = await
  self._detector.detect(text)` then `return GuardVerdict(flagged=bool(residual),
  detections=tuple(residual))`.

All the heavy machinery (structured schema, prompt templating, occurrence
location, fail-open on malformed output) is `LLMDetector`'s, reused as-is. The
guard adds only the default prompt and the verdict conversion.

`_GUARD_PROMPT` is the v1 guard prompt adapted: it tells the model it is auditing
already-anonymized text, to flag only residual clear-form PII, and to ignore
placeholders of the form `<<LABEL:N>>` or `<<LABEL:HEX>>`. It contains a
`{labels}` placeholder, filled by `LLMDetector` with the internal labels.

## Import safety and exports

The module is guarded: `if importlib.util.find_spec("langchain_core") is None:
raise ImportError("LLMGuardRail requires ... pip install piighost[llm]")`. After
the guard it imports `BaseChatModel` (for the annotation, `# noqa: E402`) and
`LLMDetector`. The module-specific guard fires first with an LLMGuardRail-named
message, matching the `moderation.py` idiom.

`LLMGuardRail` is added to `components/guard/__init__.py`: the package already
exposes `ModerationGuardRail` via a lazy `def __getattr__`, so `LLMGuardRail`
gets a second lazy branch and an `__all__` entry. The eager imports
(`AnyGuardRail`, `GuardVerdict`, `DetectorGuardRail`) are unchanged, so importing
the package stays extra-free.

## Errors

No new exception type. The guard returns a verdict; raising `PIIRemainingError`
is the caller's job. An ambiguous label reverse-map surfaces as
`LabelMappingError`, inherited from the internal `LLMDetector`'s base.

## Testing

`langchain_core` is installed in the dev venv, so these tests run (they are still
guarded with `pytest.importorskip("langchain_core")` for environments without
the extra). A fake `BaseChatModel` returns canned structured output, reusing the
fake pattern from `tests/components/detector/test_llm.py`.

Cases:

- the guard satisfies the `AnyGuardRail` protocol (`isinstance`);
- a clean text, where the fake model returns no entities, yields an unflagged
  verdict with empty `detections`;
- a residual leak, where the fake model returns an entity present in the text,
  yields a flagged verdict whose `detections` carry it;
- a custom `prompt` is forwarded to the internal detector (constructing with a
  custom prompt and confirming detection still works, so the forwarding path is
  exercised).

`LLMGuardRail` is not added to the `PUBLIC_API` list in
`tests/regression/test_imports.py`, because a `hasattr` probe would trigger its
lazy import and fail when the extra is absent. Its import behavior is covered by
`test_every_module_imports_cleanly`, which tolerates the `piighost[llm]`
ImportError.

## Out of scope

- `from_config` and config models (the config block is later; the `model | str`
  constructor absorbs model loading).
- Dynamic placeholder-grammar awareness (reading the actual factory's token
  grammar into the prompt); the default prompt hardcodes the `<<LABEL:N>>`
  grammar of the counter and hash factories, and a custom factory with a
  different grammar needs a custom prompt.
- Re-adding a token-overlap filter; the port is token-free by design.
- Changes to `LLMDetector`, the pipeline, or the `AnyGuardRail` port.
