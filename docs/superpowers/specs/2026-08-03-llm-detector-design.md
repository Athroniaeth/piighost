# LLM Detector Design

Design spec for Spec C of the detector-adapters block of the PIIGhost v2 rewrite.
Internal design document, French prose, English code identifiers.

## Context

The v2 rewrite has the detector port `AnyDetector`, the pure adapters from Spec A
(`RegexDetector`, catalogs, `CompositeDetector`), and the NER adapters from Spec B
(`BaseNERDetector` + gliner2/spacy/transformers). This spec covers the last of
the three detector sub-projects:

- Spec A (done) : regex detector and pattern catalogs.
- Spec B (done) : NER detectors over `BaseNERDetector`.
- **Spec C (this document)** : `LLMDetector`.

The v1 `LLMDetector` (`src/v1_piighost/detector/llm.py`) is the reference.

## Goal

Ship an `LLMDetector` that asks a LangChain chat model to extract PII as
structured `(text, label)` pairs, locates each extracted value in the source
text, and emits detections, reusing the label-mapping machinery of
`BaseNERDetector`.

## Key decisions

- **Reuse `BaseNERDetector`.** An LLM returns `(text, label)` pairs without
  character spans, unlike an NER model, but the label-mapping and filtering
  logic is identical. So `LLMDetector` extends `BaseNERDetector` and implements
  only `_raw_detect`, letting the base normalize labels, build the reverse
  lookup (raising `LabelMappingError` on ambiguity), relabel native to external,
  and drop unmapped. `labels` is required, since the structured schema is built
  from them.
- **model or name in the constructor.** Like the NER adapters, the chat model is
  passed either as a loaded `BaseChatModel` or as a `str` model name loaded via
  `langchain.chat_models.init_chat_model(model, model_provider=provider)`
  (imported lazily on the str path, since `init_chat_model` needs the full
  `langchain` package, not just `langchain-core`). This absorbs model loading, so
  no `from_config` is needed; the later config block forwards a name string. The
  `llm` extra therefore pins both `langchain-core` and `langchain`.
- **LangChain prompt templating.** The prompt is composed with
  `ChatPromptTemplate`, LangChain's own variable substitution, rather than a
  manual `str.format`.
- **Fail-open at the detector.** Malformed or empty structured output logs a
  warning and yields no detections rather than raising, so one bad LLM response
  does not crash the pipeline. Pair with a guard rail for a fail-closed final
  check.

## Architecture

Ports and adapters. `LLMDetector(BaseNERDetector)` lives at
`src/piighost/components/detector/llm.py`, behind the `llm` extra
(`langchain-core`, which pulls in `pydantic` for the schema).

`_raw_detect(self, text: str) -> list[Detection]` is async and awaits the chain
directly (an LLM call is async I/O, so it does not use the base's
`_run_blocking` thread offload):

1. Return `[]` immediately when `text` is empty.
2. Format the messages with LangChain's substitution and call the structured
   model: `messages = self._prompt_template.format_messages(labels=<internal
   labels joined by ", ">, text=text)` then `result = await
   self._structured.ainvoke(messages)`.
3. Read `entities = getattr(result, "entities", None)`. When it is `None` (the
   provider did not comply with the schema), log a warning and return `[]`.
4. For each extracted entity, find every occurrence of `entity.text` in the
   source via `find_all_word_boundary` (from `piighost.text`), and emit one
   `Detection(span=Span(start, end), text=text[start:end], label=<native label>,
   confidence=1.0)` per occurrence. A hallucinated value absent from the source
   yields nothing, so it is silently ignored.

The base then relabels the native labels to external and drops unmapped ones.

## Constructor, schema, and prompt

`__init__(self, model: BaseChatModel | str, labels: list[str] | dict[str, str],
prompt: str | None = None, provider: str | None = None)`:

- Calls `super().__init__(labels)` (no `max_concurrency`; the base semaphore
  serves synchronous offloaded models, and the LLM call is already async).
- When `model` is a `str`, loads it with `init_chat_model(model,
  model_provider=provider)`; otherwise uses the instance as-is.
- Builds the structured-output schema from `internal_labels`, stores the
  structured model `self._structured = model.with_structured_output(self._schema)`
  and the prompt template `self._prompt_template =
  ChatPromptTemplate.from_messages([("system", self._prompt), ("human",
  "{text}")])`. These are kept separate (rather than piped into one LCEL chain)
  so the structured model can be faked with a plain object exposing `ainvoke`.
- Stores the prompt string, defaulting to a built-in PII-extraction template
  when `None`.

Structured schema (as v1): a helper `_make_schema(labels)` builds a runtime
`Enum` of the labels, then a pydantic model `_Extraction` with `entities:
list[_Entity]`, where `_Entity` has `text: str` and `label: <LabelEnum>`. When
serialized to JSON Schema by `with_structured_output`, the enum constrains the
LLM to valid labels only. The functional `Enum` form and the absent pydantic
import need pyrefly and ruff suppressions, as in v1.

Prompt: a default PII-extraction template with a `{labels}` placeholder,
substituted by LangChain from the `internal_labels`. A custom prompt may be
passed; it must contain `{labels}` and, per LangChain's f-string format, double
any literal curly brace as `{{` / `}}`. The untrusted source text is passed as
the value of the `{text}` variable, which LangChain inserts literally without
re-scanning, so curly braces in the text are safe.

## Import safety and exports

`components/detector/llm.py` is guarded: `if
importlib.util.find_spec("langchain_core") is None: raise ImportError(... "pip
install piighost[llm]")`, with the optional imports (`langchain_core`,
`pydantic`) after the guard, each carrying `# pyrefly: ignore[missing-import]`
and `# noqa: E402`.

`LLMDetector` is exposed lazily from `components/detector/__init__.py`. That
package currently imports the pure detectors eagerly; a new `def __getattr__(
name: str) -> Any` is added that imports `LLMDetector` on demand, so accessing it
triggers the `llm` extra's import only then. The eager pure-detector imports are
unchanged, so importing the package stays extra-free. `__all__` gains
`LLMDetector`.

## Errors

No new exception type. An ambiguous label reverse-map raises `LabelMappingError`,
inherited from `BaseNERDetector`.

## Testing

`langchain_core` and `pydantic` are absent from the dev venv, so the same rules
as Spec B apply: the module import is guarded, tests use
`pytest.importorskip("langchain_core")` and skip locally, and pyrefly resolves
the optional imports via suppressions.

### Unit, fake model, `importorskip` (run when the extra is present)

A fake `BaseChatModel` whose `with_structured_output(schema)` returns a fake
runnable whose `ainvoke` returns a canned object with an `entities` attribute.
Cases:

- an extracted value present once yields one detection at the right span, with
  the label relabeled through the base;
- an extracted value present several times yields one detection per occurrence;
- a hallucinated value absent from the source yields nothing;
- a `None`-shaped structured output (no `entities`) yields `[]` and logs a
  warning (fail-open);
- an empty input text yields `[]` without calling the model;
- the adapter satisfies the `AnyDetector` protocol.

### Regression

`LLMDetector` is not added to the `PUBLIC_API` list in
`tests/regression/test_imports.py`, because a `hasattr` probe would trigger its
lazy import and fail when the extra is absent. Its import behavior is covered by
`test_every_module_imports_cleanly`, which tolerates the `piighost[llm]`
ImportError.

## Out of scope

- `from_config` and config models (the config block is later; the `model | str`
  constructor absorbs model loading).
- Retrying or repairing malformed LLM output beyond the fail-open guard.
- Any change to the pipeline, the `AnyDetector` port, or `BaseNERDetector`.
- A real-provider integration test (needs API keys); the fake-model unit tests
  cover the adapter's logic.
