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
# ]
#
# [tool.uv.sources]
# piighost = { path = "../..", editable = true }
# ///
"""Structured extraction of a French notarial sale deed.

Pipeline:
    1. ``pipeline.anonymize`` runs a CompositeDetector (GLiNER2 +
       regex packs + custom cadastral / date_fr / case_number) and
       then an LLMGuardRail final check that raises
       ``PIIRemainingError`` if the detectors missed any clear-text
       PII. Nothing leaked reaches the LLM.
    2. Send the anonymized text to Mistral via ``instructor`` to fill
       the ``SaleDeed`` Pydantic schema; the model echoes placeholders
       verbatim into nested fields.
    3. Round-trip the JSON through the captured entities to restore
       the real values, validate back into ``SaleDeed``.

Run with:
    uv run examples/llm/notarial_extraction.py
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Literal

import instructor
from dotenv import load_dotenv
from langchain_mistralai import ChatMistralAI
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

Monsieur Patrick Durand, né le 15 mars 1968, demeurant 27 avenue
des Tilleuls, 69003 Lyon, ci-après dénommé LE VENDEUR,

Madame Claire Moreau, née le 02 juillet 1985, demeurant 8
boulevard Haussmann, 75009 Paris, ci-après dénommée L'ACHETEUR.

Le VENDEUR vend à L'ACHETEUR, qui accepte, le bien suivant: maison
d'habitation sise 12 rue des Acacias, 33000 Bordeaux, cadastrée section
AB 1234, d'une surface habitable de 145 m².

Prix convenu: 487 000 EUR, payable par virement sur le compte
FR76 3000 1000 0123 4567 8901 234 ouvert au nom du vendeur.

Fait le 06 mai 2026.
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
    # GLiNER2 labels are passed as a ``{external: internal}`` mapping:
    # the *internal* phrasing (right side) is what the model sees as
    # the entity-type prompt; the *external* label (left side) is what
    # piighost emits in placeholders. Plain words like ``PERSON`` /
    # ``ADDRESS`` work, but a short natural-language phrase (e.g.
    # ``person name without civility title``) significantly tightens
    # what GLiNER2 captures: titles like "Madame" no longer get
    # absorbed into the PERSON span, and the address span actually
    # covers the full street + postal + city instead of just the city.
    # Threshold 0.4 caught everything we test for; 0.5 missed full
    # addresses, 0.3+ flooded with substrings.
    # No LOCATION label: GLiNER2 with both LOCATION and ADDRESS in its
    # vocabulary picks LOCATION over ADDRESS for short addresses (e.g.
    # ``12 rue des Acacias, 33000 Bordeaux`` becomes ``12 rue des
    # Acacias, 33000 <<LOCATION>>`` instead of a single ADDRESS span),
    # so the LLM ends up seeing a partial street + zip in clear. The
    # SAMPLE_DEED above is therefore written so that every city only
    # appears as the trailing component of a full street address; if
    # you want to anonymize standalone city mentions in your own
    # deeds, you must either (a) preprocess the source text to inline
    # them into addresses, or (b) accept reduced ADDRESS coverage and
    # add LOCATION here plus to the guardrail labels.
    gliner = Gliner2Detector(
        model=GLiNER2.from_pretrained("fastino/gliner2-multi-v1"),
        labels={
            "PERSON": "person name without civility title",
            "ADDRESS": "complete street address",
            "ORGANIZATION": "company or organization",
            "DATE": "date of birth or sale date",
        },
        threshold=0.4,
        flat_ner=True,
    )
    # Defence-in-depth regex on top of GLiNER2:
    # - EU/FR packs cover IBAN, SIREN, NIR, etc.; GENERIC covers email,
    #   phone, IPV4. CREDIT_CARD is dropped from GENERIC because its
    #   12-18 digit pattern otherwise steals an IBAN substring under
    #   the highest-confidence-first resolver (regex matches all hit
    #   confidence 1.0, ties go to the first emitter, GENERIC was
    #   merged before EU).
    # - CADASTRAL_REF is notarial-specific (e.g. ``AB 1234``).
    # - DATE_FR catches French long-form dates that GLiNER2 misses on
    #   short documents (e.g. ``15 mars 1968``).
    # - CASE_NUMBER catches the office-internal dossier reference
    #   (e.g. ``2026/AV/01287``).
    generic_minus_credit_card = {
        k: v for k, v in GENERIC_PATTERNS.items() if k != "CREDIT_CARD"
    }
    regex = RegexDetector(
        patterns={
            **generic_minus_credit_card,
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
    # LLMGuardRail re-validates the anonymized output to catch any
    # PII the detectors missed. The check happens inside
    # ``pipeline.anonymize`` and raises ``PIIRemainingError`` before
    # the leaked text ever reaches the LLM. In production, prefer a
    # cheaper model (e.g. ``mistral-small``) for this binary detection
    # pass.
    # Guardrail label set mirrors what the upstream detectors are
    # configured to find. Including LOCATION here would trip on the
    # standalone city mentions intentionally left in clear above.
    # Including ADDRESS catches the case where a future edit to the
    # deed introduces a street that the detectors miss.
    #
    # ``temperature=0`` is essential: the default sampling makes the
    # guard wildly non-deterministic, occasionally flagging civility
    # titles, units, or prices as PII. The custom prompt below makes
    # the model's job explicit so the binary check is as boring and
    # reliable as possible.
    guard_prompt = (
        "You audit text that has already been anonymized. Find PII "
        "still in clear form, matching these labels:\n"
        "{labels}\n\n"
        "Strict rules:\n"
        "- Tokens like <<PERSON:1>>, <<DATE:2>>, <<ADDRESS:3>>, "
        "<<IBAN:1>> are PLACEHOLDERS. Never flag them.\n"
        "- Civility titles (Maître, Monsieur, Madame, Me, Mr, Mrs, "
        "M., Mme, Dr, Doctor) are NOT PII.\n"
        "- Quantities, units, surfaces (145 m², 50 kg, 100 L) are "
        "NOT PII.\n"
        "- Prices and currency amounts (487 000 EUR, $100) are NOT "
        "PII.\n"
        "- Generic role words (vendor, buyer, parties, seller, "
        "VENDEUR, ACHETEUR) are NOT PII.\n"
        "- Only flag concrete identifying real-world values.\n"
        "- If no clear-form PII remains, return an empty list."
    )
    guard = LLMGuardRail(
        model=ChatMistralAI(
            model=os.getenv("MISTRAL_MODEL", "mistral-large-2512"),
            api_key=os.environ["MISTRAL_API_KEY"],
            temperature=0,
        ),
        labels=["PERSON", "ADDRESS", "ORGANIZATION", "EMAIL", "PHONE", "IBAN"],
        prompt=guard_prompt,
    )
    return AnonymizationPipeline(
        detector=detector,
        anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
        guard_rail=guard,
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


async def main() -> None:
    load_dotenv(Path(__file__).with_name(".env"))
    if not os.getenv("MISTRAL_API_KEY"):
        raise SystemExit(
            "MISTRAL_API_KEY is not set. Copy examples/llm/.env.example "
            "to examples/llm/.env and fill it in."
        )

    pipeline = build_pipeline()

    # ``pipeline.anonymize`` runs the LLMGuardRail at the end and
    # raises ``PIIRemainingError`` if the detectors missed anything.
    # Catching here means the LLM call below never sees leaked PII.
    try:
        anonymized_text, entities = await anonymize(pipeline, SAMPLE_DEED)
    except PIIRemainingError as exc:
        print("[guardrail] FAIL: residual PII detected in the anonymized deed")
        for detection in exc.detections:
            print(f"  - {detection.label}: {detection.text!r} at {detection.position}")
        raise SystemExit(1) from exc
    print(f"[anonymized deed]\n{anonymized_text}\n")
    print(f"[entities captured] {len(entities)} entities")
    print("[guardrail] PASS\n")

    extracted_json = await extract(anonymized_text)
    print(
        f"[anonymized JSON]\n"
        f"{json.dumps(json.loads(extracted_json), indent=2, ensure_ascii=False)}\n"
    )

    deed = await deanonymize(pipeline, extracted_json, entities)
    print(f"[deanonymized SaleDeed]\n{deed.model_dump_json(indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())
