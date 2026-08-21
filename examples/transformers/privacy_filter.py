# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "piighost[transformers]",
# ]
#
# [tool.uv.sources]
# piighost = { path = "../..", editable = true }
# ///
"""Detect and anonymize PII with OpenAI's privacy-filter model, fully local.

openai/privacy-filter is a token-classification NER that tags PII spans. This
wraps it as a piighost TransformersDetector and runs a full anonymize then
restore over a thread, with no network beyond the one-time weight download. The
Hugging Face pipeline is built here with aggregation_strategy, so a whole entity
comes back as one span instead of per-subtoken fragments, and trust_remote_code,
because the model ships a custom architecture. The labels map renames the
model's native labels to piighost's and drops the rest.

The first run downloads the model weights. Run with:
uv run examples/transformers/privacy_filter.py
"""

import asyncio

from transformers import pipeline  # pyrefly: ignore[missing-import]

from piighost.components.detector.ner import TransformersDetector
from piighost.pipeline import ThreadAnonymizationPipeline

THREAD = "demo"

TEXT = "Email Alice Johnson at alice.johnson@example.com or call 415-555-0142."

LABELS = {
    "private_person": "PERSON",
    "private_email": "EMAIL",
    "private_phone": "PHONE",
    "private_address": "ADDRESS",
    "private_url": "URL",
    "private_date": "DATE",
    "account_number": "ACCOUNT_NUMBER",
    "secret": "SECRET",
}


async def main() -> None:
    """Build the detector over privacy-filter, anonymize a text, then restore it."""
    ner = pipeline(
        "token-classification",
        model="openai/privacy-filter",
        aggregation_strategy="simple",
        trust_remote_code=True,
    )
    detector = TransformersDetector(pipeline=ner, labels=LABELS, threshold=0.5)
    thread_pipeline = ThreadAnonymizationPipeline(detector)

    anonymized = await thread_pipeline.anonymize(TEXT, THREAD)
    restored = await thread_pipeline.deanonymize(anonymized.text, THREAD)

    print("== original ==")
    print(f"  {TEXT}")
    print("== anonymized (what a model would see) ==")
    print(f"  {anonymized.text}")
    print("== restored ==")
    print(f"  {restored}")


if __name__ == "__main__":
    asyncio.run(main())
