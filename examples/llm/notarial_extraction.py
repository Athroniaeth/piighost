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
from datetime import date
from pathlib import Path
from typing import Literal, TypedDict

import instructor
from dotenv import load_dotenv
from langchain_mistralai import ChatMistralAI
from openai import AsyncOpenAI
from pydantic import BaseModel

# piighost types used in the State annotation; runtime imports come later
from piighost.models import Entity

from gliner2 import GLiNER2

from piighost.anonymizer import Anonymizer
from piighost.detector import CompositeDetector, RegexDetector
from piighost.detector.gliner2 import Gliner2Detector
from piighost.detector.patterns import (
    EU_PATTERNS,
    FR_PATTERNS,
    GENERIC_PATTERNS,
)
from piighost.guard_llm import LLMGuardRail
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
        text = text.replace(token, original)
    return SaleDeed.model_validate_json(text)


class ExtractionState(TypedDict):
    raw_text: str
    anonymized_text: str
    entities: list[Entity]
    extracted_json: str
    deanonymized: SaleDeed


async def main() -> None:
    load_dotenv(Path(__file__).with_name(".env"))
    if not os.getenv("MISTRAL_API_KEY"):
        raise SystemExit(
            "MISTRAL_API_KEY is not set. Copy examples/llm/.env.example "
            "to examples/llm/.env and fill it in."
        )

    pipeline = build_pipeline()

    anonymized_text, entities = await anonymize(pipeline, SAMPLE_DEED)
    print(f"[anonymized deed]\n{anonymized_text}\n")
    print(f"[entities captured] {len(entities)} entities\n")

    extracted_json = await extract(anonymized_text)
    print(
        f"[anonymized JSON]\n"
        f"{json.dumps(json.loads(extracted_json), indent=2, ensure_ascii=False)}\n"
    )

    await guardrail(extracted_json)
    print("[guardrail] PASS\n")

    deed = await deanonymize(pipeline, extracted_json, entities)
    print(f"[deanonymized SaleDeed]\n{deed.model_dump_json(indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())
