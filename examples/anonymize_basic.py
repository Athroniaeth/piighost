# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost"]
#
# [tool.uv.sources]
# piighost = { path = "..", editable = true }
# ///
"""Anonymize a text and restore it with the base pipeline.

Every occurrence of a value shares one placeholder, so the mapping reverses
cleanly. Run with: uv run examples/anonymize_basic.py
"""

import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.pipeline import AnonymizationPipeline
from piighost.components.placeholder import LabelCounterPlaceholderFactory


async def main() -> None:
    """Build a pipeline, anonymize a text, then deanonymize it back."""
    ph_factory = LabelCounterPlaceholderFactory()
    pipeline = AnonymizationPipeline(
        ExactMatchDetector({"Emma": "PERSON", "Lyon": "LOCATION"}),
        ExactEntityLinker(),
        Anonymizer(ph_factory),
    )

    text = "Emma lives in Lyon, and Emma loves Lyon."
    result = await pipeline.anonymize(text)
    restored = pipeline.deanonymize(result.text, result.tokens)

    print("original:  ", text)
    print("anonymized:", result.text)
    print("restored:  ", restored)


if __name__ == "__main__":
    asyncio.run(main())
