# Notarial document extraction example — design

**Status:** approved
**Date:** 2026-05-06
**Target file:** `examples/llm/notarial_extraction.py` (PEP 723 inline-metadata script)
**Stack:** piighost + LangGraph 1.2+ + instructor + Mistral `mistral-large-2512`

## Goal

Add a self-contained example showing how to extract structured data
from a French notarial sale deed into a typed Pydantic schema, with
PII anonymized before the LLM and a final guardrail to catch any
PII hallucinated by the model.

The example complements the existing `examples/llm/instructor_structured.py`
(which uses `instructor` directly without an orchestrator) by showing
the same idea wired through a small LangGraph state machine, with a
realistic-compact schema and an end-of-pipeline `LLMGuardRail`.

## Non-goals

- No PDF ingestion: input is a hardcoded multi-paragraph French text
  in the script itself, simulating an extracted notarial deed.
- No persistence layer: anonymization cache is the in-memory default.
- No tests: this is an example script, not library code; the
  `__main__` block doubles as a smoke test.
- No production hardening: secrets via `.env`, no retry policies
  beyond what `instructor` provides natively.

## Architecture

A linear LangGraph state graph with four nodes:

```
input_text → anonymize → extract → guardrail → deanonymize → SaleDeed
```

LangGraph is structurally overkill for a four-step linear pipeline;
the example uses it anyway to (a) honour the user request to combine
LangGraph and instructor, (b) document the pattern for when conditional
branches are added later (e.g., retry on guardrail trip, fallback to a
simpler schema). A header comment in the script makes this trade-off
explicit.

The `PIIAnonymizationMiddleware` from `piighost.middleware` is **not**
used here: it would auto-deanonymize the model response in `aafter_model`,
which would defeat the purpose of preserving placeholders verbatim
through `instructor`'s structured output. Instead, anonymize and
deanonymize are explicit graph nodes, giving full control over the
deanonymization moment.

### State

```python
class ExtractionState(TypedDict):
    raw_text: str
    anonymized_text: str
    entities: list[Entity]
    extracted_json: str       # Pydantic JSON dump (placeholders verbatim)
    deanonymized: SaleDeed    # final result
```

### Node responsibilities

- **`anonymize`** — runs `pipeline.anonymize(state["raw_text"])`,
  populates `anonymized_text` and `entities`.
- **`extract`** — calls `instructor.from_openai(AsyncOpenAI(base_url=..., api_key=...))`
  with `response_model=SaleDeed` on the anonymized text, dumps the
  resulting Pydantic instance to JSON (placeholders verbatim) into
  `extracted_json`.
- **`guardrail`** — runs `LLMGuardRail(model=ChatMistralAI(...)).check(extracted_json)`.
  On `PIIRemainingError`, the exception propagates: LangGraph stops the
  graph, the `__main__` block catches and prints a diagnostic.
- **`deanonymize`** — recomputes the placeholder-to-entity map by
  feeding the captured `entities` back into the pipeline's
  `ph_factory.create(entities)`, then string-replaces each token in
  `extracted_json` with the original value. Validates the resulting
  JSON back into `SaleDeed`, stores in `deanonymized`. The pipeline's
  `deanonymize()` method is **not** used here because it relies on a
  cache keyed by the exact anonymized text it once produced; the JSON
  dump is a different string the cache has never seen.

## Detector composition

```python
gliner = Gliner2Detector(
    model=GLiNER2.from_pretrained("fastino/gliner2-multi-v1"),
    labels=["PERSON", "LOCATION", "ORGANIZATION", "DATE"],
    threshold=0.5,
    flat_ner=True,
)
regex = RegexDetector(patterns={
    **GENERIC_PATTERNS,   # EMAIL, PHONE, IPV4
    **EU_PATTERNS,        # IBAN, EU_VAT
    **FR_PATTERNS,        # FR_NIR, FR_SIREN…
    "CADASTRAL_REF": r"\b[A-Z]{1,2}\s\d{1,4}\b",
})
detector = CompositeDetector([gliner, regex])
```

Span conflicts resolved by the default `ConfidenceSpanConflictResolver`
(highest-confidence detection wins). Entities are linked by the default
`ExactEntityLinker` (word-boundary regex sweep), which catches casing
variants like `Patrick` vs `patrick` across the document.

## Guardrail wiring

```python
guardrail = LLMGuardRail(
    model=ChatMistralAI(model="mistral-large-2512", api_key=...),
    labels=["PERSON", "LOCATION", "ORGANIZATION", "EMAIL", "PHONE", "IBAN"],
)
await guardrail.check(state["extracted_json"])
```

The guardrail runs on the JSON dump (placeholders verbatim) rather
than the raw model output text, so the residual-PII check is performed
exactly on what would be deanonymized next. Using the same
`mistral-large-2512` for the guardrail is intentional for this demo;
a code comment notes that production setups should consider a smaller
model (e.g. `mistral-small`) for the binary detection task.

## Pydantic schema

```python
class Party(BaseModel):
    full_name: str
    birth_date: date | None
    address: str

class Property(BaseModel):
    address: str
    cadastral_ref: str             # e.g. "AB 1234"
    surface_m2: int | None

class Price(BaseModel):
    amount_eur: int
    currency: Literal["EUR"] = "EUR"

class SaleDeed(BaseModel):
    seller: Party
    buyer: Party
    property: Property
    price: Price
    sale_date: date
    notary_office: str
    case_number: str | None
```

`Literal["EUR"]` rather than a free-form string: `instructor` uses the
schema constraint to filter out hallucinated currency codes.

## System prompt to the LLM

Same shape as the existing `instructor_structured.py`: instruct the
model that the input is anonymized with `<<LABEL:N>>` tokens, that it
must copy them verbatim into the corresponding fields, and that it
must never invent a name or strip the brackets. Adapted to mention
nested fields and French notarial vocabulary.

## Sample input

A 15-line hardcoded French text simulating an extracted notarial
sale deed. Must contain at minimum:

- two parties (seller, buyer) with full names, birth dates, addresses
- one notary office name
- one property with address + cadastral reference
- one explicit price in EUR
- one signing date
- one IBAN (to exercise `EU_PATTERNS`)
- one case number (to exercise the regex pack)

Stored as a module-level string `SAMPLE_DEED`. Easy to swap for a
file read later.

## Error handling

- `PIIRemainingError` (guardrail trip) → propagated out of the graph;
  the `__main__` block catches it and prints which detections leaked.
- `instructor.RetryError` (schema invalid after N retries) → propagated;
  `instructor` is configured with `max_retries=2`.
- Missing `MISTRAL_API_KEY` → fail fast at startup with a clear message
  before loading GLiNER2 (which is the slow part).

## Config

`.env` next to the script (mirrors `instructor_structured.py`):

```
MISTRAL_API_KEY=...
MISTRAL_BASE_URL=https://api.mistral.ai/v1
MISTRAL_MODEL=mistral-large-2512
```

The Mistral API exposes an OpenAI-compatible endpoint, so `instructor`
drives it through `AsyncOpenAI(base_url=MISTRAL_BASE_URL, ...)`. The
guardrail uses `langchain-mistralai`'s native `ChatMistralAI` because
`LLMGuardRail` expects a LangChain `BaseChatModel`.

## PEP 723 dependencies

```python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "piighost[cache,gliner2,llm]",
#   "gliner2>=1.2.0",
#   "instructor>=1.6.0",
#   "openai>=1.50.0",
#   "pydantic>=2.0",
#   "python-dotenv>=1.0.0",
#   "langchain>=1.2",
#   "langchain-mistralai>=0.2",
#   "langgraph>=1.2",
# ]
#
# [tool.uv.sources]
# piighost = { path = "../..", editable = true }
# ///
```

## Run command

```bash
uv run examples/llm/notarial_extraction.py
```

Expected output: the anonymized text, the structured JSON with
placeholders, the same JSON deanonymized into the original values.

## Out of scope (deferred)

- Multi-deed batch mode.
- Streaming partial extraction (instructor's partial mode).
- Persistent cache (Redis backend) for cross-run deanonymization.
- Integration tests (would require mocking Mistral or a fixture
  cassette).
- A non-instructor variant using LangChain's `with_structured_output`
  alone (already covered indirectly in the existing graph example).
