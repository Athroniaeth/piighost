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
#   "langgraph>=1.1",
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
from pathlib import Path
from typing import Literal, TypedDict

import instructor
from dotenv import load_dotenv
from langchain_mistralai import ChatMistralAI
from langgraph.graph import END, START, StateGraph
from openai import AsyncOpenAI
from pydantic import BaseModel

from gliner2 import GLiNER2

from piighost.anonymizer import Anonymizer
from piighost.detector import CompositeDetector, RegexDetector
from piighost.detector.gliner2 import Gliner2Detector
from piighost.detector.patterns import (
    EU_PATTERNS,
    FR_PATTERNS,
    GENERIC_PATTERNS,
)
from piighost.exceptions import PIIRemainingError
from piighost.guard_llm import LLMGuardRail
from piighost.models import Entity
from piighost.pipeline.base import AnonymizationPipeline
from piighost.placeholder import LabelCounterPlaceholderFactory


SAMPLE_DEED = """\
ACTE DE VENTE IMMOBILIÈRE — DOSSIER N° 2026/AV/01287

Par devant Maître Sophie Lambert, notaire associée de l'office notarial
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
    # Stored as a free-form string: while anonymized, the field carries
    # a ``<<DATE:N>>`` placeholder; after deanonymize it carries the
    # original locale-specific phrasing (e.g. ``"15 mars 1968"``). A
    # ``date`` typing would force the model to either drop the
    # placeholder or hallucinate a numeric date.
    birth_date: str | None
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
    sale_date: str
    notary_office: str
    case_number: str | None


SYSTEM_PROMPT = (
    "You extract structured notarial sale deeds from partially "
    "anonymized French text into the provided JSON schema.\n"
    "\n"
    "Some values in the input have been anonymized: they appear as "
    "placeholders of the form <<LABEL:N>>, e.g. <<PERSON:1>>, "
    "<<ADDRESS:2>>, <<DATE:1>>, <<IBAN:1>>. Treat each placeholder as "
    "the real value it replaces and copy it verbatim into the output "
    "JSON, with the surrounding double angle brackets, the colon, and "
    "the trailing number intact.\n"
    "\n"
    "Strict rule: only use a placeholder token if you see that exact "
    "token (same label, same number) in the input text. Never invent a "
    "placeholder, never increment its number, never substitute a "
    "different label. If a value is NOT anonymized in the input (you "
    "see it in clear, like ``15 mars 1968`` or ``Lyon``), copy it "
    "verbatim from the source text, do not replace it with a fabricated "
    "placeholder.\n"
    "\n"
    "Numeric fields such as ``surface_m2`` and ``price.amount_eur`` are "
    "never anonymized; extract the integer value present in the text."
)


def build_pipeline() -> AnonymizationPipeline:
    """Compose GLiNER2 (open NER) with regex packs (FR / EU / generic)
    plus a custom French cadastral reference pattern (e.g. ``AB 1234``).
    Span conflicts are resolved by the default
    ``ConfidenceSpanConflictResolver`` (highest confidence wins)."""
    gliner = Gliner2Detector(
        model=GLiNER2.from_pretrained("fastino/gliner2-multi-v1"),
        labels=["PERSON", "LOCATION", "ADDRESS", "ORGANIZATION", "DATE"],
        threshold=0.5,
        flat_ner=True,
    )
    # Defence-in-depth regex on top of GLiNER2:
    # - GENERIC/EU/FR packs cover IBAN, SIREN, NIR, etc.
    # - CADASTRAL_REF is notarial-specific (e.g. ``AB 1234``).
    # - DATE_FR catches French long-form dates that GLiNER2 misses on
    #   short documents (e.g. ``15 mars 1968``).
    # - CASE_NUMBER catches the office-internal dossier reference
    #   (e.g. ``2026/AV/01287``).
    regex = RegexDetector(
        patterns={
            **GENERIC_PATTERNS,
            **EU_PATTERNS,
            **FR_PATTERNS,
            "CADASTRAL_REF": r"\b[A-Z]{1,2}\s\d{1,4}\b",
            "DATE_FR": (
                r"\b\d{1,2}\s+"
                r"(?:janvier|f[ée]vrier|mars|avril|mai|juin|juillet|"
                r"ao[ûu]t|septembre|octobre|novembre|d[ée]cembre)\s+"
                r"\d{4}\b"
            ),
            "CASE_NUMBER": r"\b\d{4}/[A-Z]{1,4}/\d{4,}\b",
        }
    )
    detector = CompositeDetector([gliner, regex])
    return AnonymizationPipeline(
        detector=detector,
        anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
    )


async def anonymize(
    pipeline: AnonymizationPipeline, text: str
) -> tuple[str, list[Entity]]:
    """Run piighost on the deed and return the anonymized text plus
    the entities captured for the later deanonymize step."""
    anonymized_text, entities = await pipeline.anonymize(text)
    return anonymized_text, entities


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
        # JSON-escape the replacement: multi-line PII (street + city
        # split by a real newline in the source text) and any embedded
        # quotes would otherwise produce invalid JSON. ``json.dumps``
        # wraps the value in quotes, so slice them off.
        text = text.replace(token, json.dumps(original, ensure_ascii=False)[1:-1])
    return SaleDeed.model_validate_json(text)


class ExtractionState(TypedDict):
    raw_text: str
    anonymized_text: str
    entities: list[Entity]
    extracted_json: str
    deanonymized: SaleDeed


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
        deed = await deanonymize(pipeline, state["extracted_json"], state["entities"])
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


async def main() -> None:
    load_dotenv(Path(__file__).with_name(".env"))
    if not os.getenv("MISTRAL_API_KEY"):
        raise SystemExit(
            "MISTRAL_API_KEY is not set. Copy examples/llm/.env.example "
            "to examples/llm/.env and fill it in."
        )

    pipeline = build_pipeline()
    graph = build_graph(pipeline)

    try:
        final_state: ExtractionState = await graph.ainvoke({"raw_text": SAMPLE_DEED})
    except PIIRemainingError as exc:
        print("[guardrail] FAIL: residual PII detected in the extracted JSON")
        for detection in exc.detections:
            print(f"  - {detection.label}: {detection.text!r} at {detection.position}")
        raise SystemExit(1) from exc

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


if __name__ == "__main__":
    asyncio.run(main())
