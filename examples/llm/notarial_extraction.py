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

from dotenv import load_dotenv
from pydantic import BaseModel

# piighost types used in the State annotation; runtime imports come later
from piighost.models import Entity


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
