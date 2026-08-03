# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost"]
#
# [tool.uv.sources]
# piighost = { path = "..", editable = true }
# ///
"""Catch residual PII with a guard rail.

The pipeline anonymizes the email it knows, and a second, stronger detector
guards the output for a different email the pipeline missed. A flagged guard
raises PIIRemainingError. Run with: uv run examples/guard_rail.py
"""

import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.guard import DetectorGuardRail
from piighost.components.linker import ExactEntityLinker
from piighost.pipeline import AnonymizationPipeline
from piighost.components.placeholder import RedactPlaceholderFactory


async def main() -> None:
    """Anonymize a text, then one whose second, unknown email trips the guard."""
    ph_factory = RedactPlaceholderFactory()
    guard_detector = ExactMatchDetector({"bob@example.com": "EMAIL"})
    pipeline = AnonymizationPipeline(
        ExactMatchDetector({"alice@example.com": "EMAIL"}),
        ExactEntityLinker(),
        Anonymizer(ph_factory),
        guard=DetectorGuardRail(guard_detector),
    )

    clean = await pipeline.anonymize("Contact alice@example.com.")
    print("clean output:", clean.text)

    # piighost.exceptions.PIIRemainingError: Anonymized text still contains PII: ['EMAIL']
    await pipeline.anonymize("Contact alice@example.com or bob@example.com.")


if __name__ == "__main__":
    asyncio.run(main())
