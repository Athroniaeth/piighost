# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost"]
#
# [tool.uv.sources]
# piighost = { path = "..", editable = true }
# ///
"""Catch residual PII with a guard rail.

The pipeline anonymizes names, and a second, stronger detector guards the
output for anything the pipeline missed. A flagged guard raises
PIIRemainingError. Run with: uv run examples/guard_rail.py
"""

import asyncio

from piighost.anonymizer import Anonymizer
from piighost.detector import ExactMatchDetector
from piighost.exceptions import PIIRemainingError
from piighost.guard import DetectorGuardRail
from piighost.linker import ExactEntityLinker
from piighost.pipeline import AnonymizationPipeline
from piighost.placeholder import RedactPlaceholderFactory


async def main() -> None:
    """Anonymize a clean text, then one whose leftover PII trips the guard."""
    ph_factory = RedactPlaceholderFactory()
    guard_detector = ExactMatchDetector({"emma@example.com": "EMAIL"})
    pipeline = AnonymizationPipeline(
        ExactMatchDetector({"Emma": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(ph_factory),
        guard=DetectorGuardRail(guard_detector),
    )

    clean = await pipeline.anonymize("Emma says hello.")
    print("clean output:", clean.text)

    try:
        await pipeline.anonymize("Emma at emma@example.com.")
    except PIIRemainingError as error:
        print("guard raised:", error)


if __name__ == "__main__":
    asyncio.run(main())
