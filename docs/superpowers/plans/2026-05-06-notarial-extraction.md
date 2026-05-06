# Notarial Extraction Example Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a self-contained PEP 723 example showing structured extraction of a French notarial sale deed using piighost + LangGraph + instructor + Mistral large.

**Architecture:** A single file at `examples/llm/notarial_extraction.py`. Build pieces first as plain async functions (anonymize → extract → guardrail → deanonymize), verify each end-to-end against a hardcoded sample, then wrap the four steps as LangGraph nodes. No pytest tests; the `__main__` block doubles as a smoke test, run via `uv run`.

**Tech Stack:** Python 3.12+, piighost (`cache,gliner2,llm`), `gliner2`, `instructor`, `openai`, `pydantic`, `python-dotenv`, `langchain>=1.2`, `langchain-mistralai>=0.2`, `langgraph>=1.2`. PEP 723 inline metadata pins everything.

---

## File structure

Single file `examples/llm/notarial_extraction.py` organized as:

1. PEP 723 inline metadata header
2. Module docstring
3. Imports
4. Constants (`SAMPLE_DEED`, `SYSTEM_PROMPT`)
5. Pydantic schemas (`Party`, `Property`, `Price`, `SaleDeed`)
6. Pipeline factory (`build_pipeline`)
7. Async step functions (`anonymize`, `extract`, `guardrail`, `deanonymize`)
8. LangGraph state + builder (`ExtractionState`, `build_graph`)
9. `main()` and `__main__` guard

A sibling `examples/llm/.env.example` documents the required env vars without committing secrets.

---

## Task 1: Scaffold the script with sample input and schemas

**Files:**
- Create: `examples/llm/notarial_extraction.py`
- Create: `examples/llm/.env.example`

- [ ] **Step 1: Create the PEP 723 header, module docstring, sample input, and Pydantic schemas**

Create `examples/llm/notarial_extraction.py`:

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
"""Structured extraction of a French notarial sale deed.

Pipeline:
    1. Anonymize the deed text with a piighost CompositeDetector
       (GLiNER2 + regex packs + custom cadastral pattern).
    2. Send the anonymized text to Mistral via ``instructor`` to fill
       the ``SaleDeed`` Pydantic schema; the model echoes placeholders
       verbatim into nested fields.
    3. Run an LLMGuardRail over the JSON dump to catch any PII the
       model might have hallucinated into free-text fields.
    4. Round-trip the JSON through the captured entities to restore
       the real values, validate back into ``SaleDeed``.

The four steps are wrapped as nodes in a small LangGraph state
machine. This is overkill for a linear flow, kept here to document the
pattern (e.g. for adding a retry edge from guardrail back to extract
in a future iteration).

Run with:
    uv run examples/llm/notarial_extraction.py
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import date
from pathlib import Path
from typing import Literal, TypedDict

from dotenv import load_dotenv
from pydantic import BaseModel

# piighost types used in the State annotation; runtime imports come later
from piighost.entity import Entity


SAMPLE_DEED = """\
ACTE DE VENTE IMMOBILIÈRE — DOSSIER N° 2026/AV/01287

Par devant Maître Sophie Lambert, notaire associé de l'office notarial
SCP Lambert & Associés, sis 14 rue de Verdun, 75008 Paris,

ONT COMPARU:

Monsieur Patrick Durand, né le 15 mars 1968 à Lyon, demeurant 27 avenue
des Tilleuls, 69003 Lyon, ci-après dénommé LE VENDEUR,

Madame Claire Moreau, née le 02 juillet 1985 à Bordeaux, demeurant 8
boulevard Haussmann, 75009 Paris, ci-après dénommée L'ACHETEUR.

Le VENDEUR vend à L'ACHETEUR, qui accepte, le bien suivant: maison
d'habitation sise 12 rue des Acacias, 33000 Bordeaux, cadastrée section
AB 1234, d'une surface habitable de 145 m².

Prix convenu: 487 000 EUR, payable par virement sur le compte
FR76 3000 1000 0123 4567 8901 234 ouvert au nom du vendeur.

Fait à Paris, le 06 mai 2026.
"""


class Party(BaseModel):
    full_name: str
    birth_date: date | None
    address: str


class Property(BaseModel):
    address: str
    cadastral_ref: str
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


SYSTEM_PROMPT = (
    "You extract structured notarial sale deeds from anonymized French "
    "text into the provided JSON schema.\n"
    "\n"
    "The input has been anonymized: real names, locations, dates, "
    "organizations, and identifiers are replaced with placeholders of "
    "the form <<LABEL:N>>, e.g. <<PERSON:1>>, <<LOCATION:2>>, "
    "<<DATE:1>>, <<IBAN:1>>. Treat each placeholder as the real value "
    "it replaces. You MUST copy each placeholder verbatim (with the "
    "surrounding double angle brackets, the colon, and the trailing "
    "number) into the corresponding field of the output JSON. Never "
    "strip the brackets, never invent a name, address, date, or "
    "identifier, never describe the placeholder format. For numeric "
    "fields like ``surface_m2`` and ``price.amount_eur``, extract the "
    "integer value present in the text; these are not anonymized."
)


class ExtractionState(TypedDict):
    raw_text: str
    anonymized_text: str
    entities: list[Entity]
    extracted_json: str
    deanonymized: SaleDeed


async def main() -> None:
    load_dotenv(Path(__file__).with_name(".env"))
    print(f"[input deed]\n{SAMPLE_DEED}\n")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Create the env example**

Create `examples/llm/.env.example`:

```
MISTRAL_API_KEY=
MISTRAL_BASE_URL=https://api.mistral.ai/v1
MISTRAL_MODEL=mistral-large-2512
```

- [ ] **Step 3: Verify the script imports and prints the sample**

Run: `uv run examples/llm/notarial_extraction.py`

Expected: The deed text is printed under `[input deed]`, no traceback. (First run will install dependencies, including `gliner2` model download deferred to later tasks.)

- [ ] **Step 4: Commit**

```bash
git add examples/llm/notarial_extraction.py examples/llm/.env.example
git commit -m "feat(examples): scaffold notarial extraction script

Bootstrap the PEP 723 single-file example with the sample sale deed,
SaleDeed/Party/Property/Price Pydantic schemas, the system prompt for
the structured extraction step, and a minimal main() that loads .env
and echoes the sample. Subsequent tasks wire the pipeline."
```

---

## Task 2: Wire the piighost CompositeDetector and anonymize the sample

**Files:**
- Modify: `examples/llm/notarial_extraction.py` (add imports, `build_pipeline`, `anonymize` step, extend `main`)

- [ ] **Step 1: Add the runtime imports for piighost**

Insert after the `from piighost.entity import Entity` line:

```python
from gliner2 import GLiNER2

from piighost.anonymizer import Anonymizer
from piighost.detector.composite import CompositeDetector
from piighost.detector.gliner2 import Gliner2Detector
from piighost.detector.patterns import (
    EU_PATTERNS,
    FR_PATTERNS,
    GENERIC_PATTERNS,
)
from piighost.detector.regex import RegexDetector
from piighost.pipeline.base import AnonymizationPipeline
from piighost.placeholder import LabelCounterPlaceholderFactory
```

- [ ] **Step 2: Add the pipeline factory**

Insert after the `SYSTEM_PROMPT` constant:

```python
def build_pipeline() -> AnonymizationPipeline:
    """Compose GLiNER2 (open NER) with regex packs (FR / EU / generic)
    plus a custom French cadastral reference pattern (e.g. ``AB 1234``).
    Span conflicts are resolved by the default
    ``ConfidenceSpanConflictResolver`` (highest confidence wins)."""
    gliner = Gliner2Detector(
        model=GLiNER2.from_pretrained("fastino/gliner2-multi-v1"),
        labels=["PERSON", "LOCATION", "ORGANIZATION", "DATE"],
        threshold=0.5,
        flat_ner=True,
    )
    regex = RegexDetector(
        patterns={
            **GENERIC_PATTERNS,
            **EU_PATTERNS,
            **FR_PATTERNS,
            "CADASTRAL_REF": r"\b[A-Z]{1,2}\s\d{1,4}\b",
        }
    )
    detector = CompositeDetector([gliner, regex])
    return AnonymizationPipeline(
        detector=detector,
        anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
    )
```

- [ ] **Step 3: Add the anonymize step function**

Insert after `build_pipeline`:

```python
async def anonymize(
    pipeline: AnonymizationPipeline, text: str
) -> tuple[str, list[Entity]]:
    """Run piighost on the deed and return the anonymized text plus
    the entities captured for the later deanonymize step."""
    anonymized_text, entities = await pipeline.anonymize(text)
    return anonymized_text, entities
```

- [ ] **Step 4: Extend `main` to call anonymize and print the result**

Replace the body of `main`:

```python
async def main() -> None:
    load_dotenv(Path(__file__).with_name(".env"))
    pipeline = build_pipeline()

    anonymized_text, entities = await anonymize(pipeline, SAMPLE_DEED)
    print(f"[anonymized deed]\n{anonymized_text}\n")
    print(f"[entities captured] {len(entities)} entities")
```

- [ ] **Step 5: Verify anonymization works end-to-end**

Run: `uv run examples/llm/notarial_extraction.py`

Expected: GLiNER2 model loads (first run downloads weights), then `[anonymized deed]` shows the sample with placeholders like `<<PERSON:1>>`, `<<LOCATION:1>>`, `<<DATE:1>>`, `<<IBAN:1>>`, `<<CADASTRAL_REF:1>>` substituted for the real names, addresses, dates, IBAN, and cadastral reference. `[entities captured]` prints a non-zero count (typically 8-12).

If `<<CADASTRAL_REF:1>>` is missing from the output, the regex did not match `AB 1234`; verify the sample contains exactly two letters, a single space, then four digits.

- [ ] **Step 6: Commit**

```bash
git add examples/llm/notarial_extraction.py
git commit -m "feat(examples): wire piighost CompositeDetector for notarial deeds

Compose GLiNER2 (PERSON/LOCATION/ORGANIZATION/DATE) with the FR + EU +
generic regex packs and a custom cadastral pattern. The anonymize step
prints the redacted deed and the entity count so the rest of the
pipeline can be built incrementally on top."
```

---

## Task 3: Run structured extraction via instructor + Mistral

**Files:**
- Modify: `examples/llm/notarial_extraction.py` (add imports, `extract` step, extend `main`)

- [ ] **Step 1: Add imports for instructor and Mistral via the OpenAI SDK**

Insert after the existing piighost imports:

```python
import instructor
from openai import AsyncOpenAI
```

- [ ] **Step 2: Add the extract step function**

Insert after `anonymize`:

```python
async def extract(anonymized_text: str) -> str:
    """Call Mistral through the OpenAI-compatible endpoint, with
    ``instructor`` enforcing the SaleDeed schema. Returns the JSON
    dump of the Pydantic instance. Placeholders like
    ``<<PERSON:1>>`` are kept verbatim in the JSON so the
    deanonymize step can substitute them later."""
    client = instructor.from_openai(
        AsyncOpenAI(
            base_url=os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1"),
            api_key=os.environ["MISTRAL_API_KEY"],
        )
    )
    deed = await client.chat.completions.create(
        model=os.getenv("MISTRAL_MODEL", "mistral-large-2512"),
        response_model=SaleDeed,
        max_retries=2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": anonymized_text},
        ],
    )
    return deed.model_dump_json()
```

- [ ] **Step 3: Fail fast on missing API key**

Insert at the top of `main` body, right after `load_dotenv(...)`:

```python
    if not os.getenv("MISTRAL_API_KEY"):
        raise SystemExit(
            "MISTRAL_API_KEY is not set. Copy examples/llm/.env.example "
            "to examples/llm/.env and fill it in."
        )
```

- [ ] **Step 4: Extend `main` to call extract and print the JSON**

Append to the end of `main`:

```python
    extracted_json = await extract(anonymized_text)
    print(f"[anonymized JSON]\n{json.dumps(json.loads(extracted_json), indent=2, ensure_ascii=False)}\n")
```

- [ ] **Step 5: Verify extraction works end-to-end**

Prerequisite: copy `examples/llm/.env.example` to `examples/llm/.env` and fill `MISTRAL_API_KEY`.

Run: `uv run examples/llm/notarial_extraction.py`

Expected: After the anonymized deed, `[anonymized JSON]` prints a pretty-printed JSON object whose `seller.full_name`, `buyer.full_name`, `property.address`, `property.cadastral_ref`, `notary_office`, `sale_date`, `seller.birth_date`, `buyer.birth_date`, and `case_number` fields contain placeholder tokens (e.g. `"full_name": "<<PERSON:1>>"`). Numeric fields `price.amount_eur` and `property.surface_m2` should be the real integers (`487000` and `145`), since they are not anonymized.

If the model strips the brackets or hallucinates real names, the system prompt is not being followed; double-check no edits crept into `SYSTEM_PROMPT`.

- [ ] **Step 6: Commit**

```bash
git add examples/llm/notarial_extraction.py
git commit -m "feat(examples): structured extraction via instructor + Mistral

Wire instructor.from_openai over the Mistral OpenAI-compatible
endpoint, with response_model=SaleDeed and max_retries=2. The model
sees only anonymized text and is instructed to copy placeholders
verbatim into nested fields, so the JSON dump still carries
<<LABEL:N>> tokens that the deanonymize step will replace."
```

---

## Task 4: Add the LLMGuardRail check on the extracted JSON

**Files:**
- Modify: `examples/llm/notarial_extraction.py` (add imports, `guardrail` step, extend `main`)

- [ ] **Step 1: Add imports for ChatMistralAI and the piighost guard**

Insert with the existing imports:

```python
from langchain_mistralai import ChatMistralAI

from piighost.guard_llm import LLMGuardRail
```

- [ ] **Step 2: Add the guardrail step function**

Insert after `extract`:

```python
async def guardrail(extracted_json: str) -> None:
    """Final defence-in-depth pass. The LLM may have hallucinated PII
    into a free-text field (for instance dropping a real notary name
    into ``notary_office`` despite the placeholder prompt); the guard
    re-runs detection on the JSON dump and raises
    ``PIIRemainingError`` if anything looks like clear-text PII.

    In production, prefer a smaller/cheaper Mistral model here (e.g.
    ``mistral-small``) since this is a binary detection task.
    """
    guard = LLMGuardRail(
        model=ChatMistralAI(
            model=os.getenv("MISTRAL_MODEL", "mistral-large-2512"),
            api_key=os.environ["MISTRAL_API_KEY"],
        ),
        labels=["PERSON", "LOCATION", "ORGANIZATION", "EMAIL", "PHONE", "IBAN"],
    )
    await guard.check(extracted_json)
```

- [ ] **Step 3: Extend `main` to call the guardrail**

Append to `main` after the `[anonymized JSON]` print:

```python
    await guardrail(extracted_json)
    print("[guardrail] PASS\n")
```

- [ ] **Step 4: Verify the guardrail passes on a clean run**

Run: `uv run examples/llm/notarial_extraction.py`

Expected: After `[anonymized JSON]`, `[guardrail] PASS` prints. No traceback.

If `PIIRemainingError` is raised, the model leaked PII into the JSON despite the placeholder prompt; this is the failure mode the guardrail is meant to surface. For the smoke test, the curated `SAMPLE_DEED` should not trigger it.

- [ ] **Step 5: Commit**

```bash
git add examples/llm/notarial_extraction.py
git commit -m "feat(examples): add LLMGuardRail check on extracted JSON

Run an LLMGuardRail (ChatMistralAI) on the anonymized JSON dump from
instructor. Catches PII the model might have hallucinated into nested
free-text fields. PIIRemainingError propagates and aborts the
pipeline; no auto-retry in this example."
```

---

## Task 5: Round-trip deanonymize the JSON back into a SaleDeed

**Files:**
- Modify: `examples/llm/notarial_extraction.py` (add `deanonymize` step, extend `main`)

- [ ] **Step 1: Add the deanonymize step function**

Insert after `guardrail`:

```python
async def deanonymize(
    pipeline: AnonymizationPipeline,
    extracted_json: str,
    entities: list[Entity],
) -> SaleDeed:
    """Restore the original PII values in the extracted JSON.

    The pipeline's own ``deanonymize()`` is keyed on the exact
    anonymized text it produced; the JSON dump is a different string
    the cache has never seen. Instead we rebuild the placeholder map
    from the captured entities via ``ph_factory.create(entities)``,
    then string-replace each token with its source value. The longest
    placeholder is replaced first to avoid prefix collisions
    (``<<PERSON:11>>`` before ``<<PERSON:1>>``).
    """
    tokens = pipeline.ph_factory.create(entities)
    replacements = sorted(
        ((token, entity.detections[0].text) for entity, token in tokens.items()),
        key=lambda pair: len(pair[0]),
        reverse=True,
    )
    text = extracted_json
    for token, original in replacements:
        text = text.replace(token, original)
    return SaleDeed.model_validate_json(text)
```

- [ ] **Step 2: Extend `main` to deanonymize and print the final**

Append to `main` after `[guardrail] PASS`:

```python
    deed = await deanonymize(pipeline, extracted_json, entities)
    print(f"[deanonymized SaleDeed]\n{deed.model_dump_json(indent=2)}")
```

- [ ] **Step 3: Verify the round-trip yields the real values**

Run: `uv run examples/llm/notarial_extraction.py`

Expected: After `[guardrail] PASS`, `[deanonymized SaleDeed]` prints the same JSON as `[anonymized JSON]` but with placeholders replaced by their original values. Spot-check: `seller.full_name` should be `Patrick Durand`, `buyer.full_name` should be `Claire Moreau`, `property.cadastral_ref` should be `AB 1234`, `notary_office` should mention `Lambert`.

If a placeholder remains in the output (e.g. `"full_name": "<<PERSON:1>>"`), the entity ordering or factory used at extraction differed from the one used here; both must come from the same pipeline instance.

- [ ] **Step 4: Commit**

```bash
git add examples/llm/notarial_extraction.py
git commit -m "feat(examples): round-trip deanonymize the extracted JSON

Rebuild the placeholder->entity map from the captured entities and
string-replace each token in the JSON dump (longest first to avoid
prefix collisions like <<PERSON:11>> shadowing <<PERSON:1>>), then
validate the restored text back into SaleDeed."
```

---

## Task 6: Wrap the four steps as a LangGraph state machine

**Files:**
- Modify: `examples/llm/notarial_extraction.py` (add LangGraph imports, `build_graph`, replace `main` body)

- [ ] **Step 1: Add the LangGraph import**

Insert with the existing imports:

```python
from langgraph.graph import END, START, StateGraph
```

- [ ] **Step 2: Add the graph builder**

Insert after `deanonymize`:

```python
def build_graph(pipeline: AnonymizationPipeline) -> "object":
    """Wire the four async steps into a LangGraph state machine.

    The flow is linear (anonymize -> extract -> guardrail ->
    deanonymize), which makes LangGraph mostly ceremonial here. Kept
    as a reference for adding a conditional edge later, e.g. routing
    back to extract on a recoverable guardrail trip.
    """

    async def anonymize_node(state: ExtractionState) -> dict:
        anonymized_text, entities = await anonymize(pipeline, state["raw_text"])
        return {"anonymized_text": anonymized_text, "entities": entities}

    async def extract_node(state: ExtractionState) -> dict:
        extracted_json = await extract(state["anonymized_text"])
        return {"extracted_json": extracted_json}

    async def guardrail_node(state: ExtractionState) -> dict:
        await guardrail(state["extracted_json"])
        return {}

    async def deanonymize_node(state: ExtractionState) -> dict:
        deed = await deanonymize(
            pipeline, state["extracted_json"], state["entities"]
        )
        return {"deanonymized": deed}

    graph = StateGraph(ExtractionState)
    graph.add_node("anonymize", anonymize_node)
    graph.add_node("extract", extract_node)
    graph.add_node("guardrail", guardrail_node)
    graph.add_node("deanonymize", deanonymize_node)
    graph.add_edge(START, "anonymize")
    graph.add_edge("anonymize", "extract")
    graph.add_edge("extract", "guardrail")
    graph.add_edge("guardrail", "deanonymize")
    graph.add_edge("deanonymize", END)
    return graph.compile()
```

- [ ] **Step 3: Replace the body of `main` with a graph invocation**

Replace `main` entirely (keep imports, schemas, and step functions intact):

```python
async def main() -> None:
    load_dotenv(Path(__file__).with_name(".env"))
    if not os.getenv("MISTRAL_API_KEY"):
        raise SystemExit(
            "MISTRAL_API_KEY is not set. Copy examples/llm/.env.example "
            "to examples/llm/.env and fill it in."
        )

    pipeline = build_pipeline()
    graph = build_graph(pipeline)

    final_state: ExtractionState = await graph.ainvoke({"raw_text": SAMPLE_DEED})

    print(f"[anonymized deed]\n{final_state['anonymized_text']}\n")
    print(f"[entities captured] {len(final_state['entities'])} entities\n")
    print(
        f"[anonymized JSON]\n"
        f"{json.dumps(json.loads(final_state['extracted_json']), indent=2, ensure_ascii=False)}\n"
    )
    print("[guardrail] PASS\n")
    print(
        f"[deanonymized SaleDeed]\n"
        f"{final_state['deanonymized'].model_dump_json(indent=2)}"
    )
```

- [ ] **Step 4: Verify the graph produces the same end state as the linear chain**

Run: `uv run examples/llm/notarial_extraction.py`

Expected: Same five sections of output as after Task 5 (`[anonymized deed]`, entity count, `[anonymized JSON]`, `[guardrail] PASS`, `[deanonymized SaleDeed]`), populated from the LangGraph final state. Spot-check `seller.full_name` is `Patrick Durand` and `property.cadastral_ref` is `AB 1234`.

If `final_state["entities"]` is empty in the deanonymize step, the per-node return dict for `anonymize_node` is dropping the `entities` key; verify it returns both `anonymized_text` and `entities`.

- [ ] **Step 5: Commit**

```bash
git add examples/llm/notarial_extraction.py
git commit -m "feat(examples): wire pipeline as a LangGraph state machine

Wrap the four async steps (anonymize, extract, guardrail, deanonymize)
as nodes in a linear StateGraph[ExtractionState]. Overkill for a
linear flow on purpose: documents the pattern for later additions
like a conditional retry edge from guardrail back to extract."
```

---

## Self-review

**Spec coverage**

- Architecture (LangGraph 4 nodes linear): Task 6.
- ExtractionState TypedDict: Task 1 declares it, Task 6 wires it.
- Pydantic SaleDeed/Party/Property/Price: Task 1.
- CompositeDetector(GLiNER2 + RegexDetector + cadastre): Task 2.
- instructor + Mistral via OpenAI-compatible endpoint, max_retries=2: Task 3.
- LLMGuardRail with ChatMistralAI on the extracted JSON: Task 4.
- Round-trip deanonymize without using the cache: Task 5.
- Sample input with parties / property / price / cadastre / IBAN / case_number / dates: Task 1 (`SAMPLE_DEED`).
- Fail fast on missing API key: Task 3 step 3.
- PEP 723 deps as listed in the spec: Task 1 step 1.
- `.env` next to script (`.env.example` shipped, `.env` gitignored by user): Task 1 step 2.
- Run command `uv run examples/llm/notarial_extraction.py`: covered in every verification step.

**Placeholder scan:** None. Every step shows the literal code or the literal command.

**Type consistency:** `Entity` imported from `piighost.entity` in Task 1, used in `ExtractionState` and the `deanonymize` signature in Task 5; `AnonymizationPipeline` is the concrete return type of `build_pipeline` and the parameter type of `anonymize`/`deanonymize`. `ExtractionState` keys (`raw_text`, `anonymized_text`, `entities`, `extracted_json`, `deanonymized`) match between Task 1 declaration, Task 6 node returns, and Task 6 main reads. `SYSTEM_PROMPT` referenced in Task 3 is defined in Task 1.
