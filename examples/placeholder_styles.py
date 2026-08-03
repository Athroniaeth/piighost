# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost"]
#
# [tool.uv.sources]
# piighost = { path = "..", editable = true }
# ///
"""Compare placeholder styles on one text.

The same pipeline runs with each factory, so only the token form differs: a
constant redaction, a label, a numbered label, a hashed label, or a mask. Run
with: uv run examples/placeholder_styles.py
"""

import asyncio

from piighost.anonymizer import Anonymizer
from piighost.detector import ExactMatchDetector
from piighost.linker import ExactEntityLinker
from piighost.pipeline import AnonymizationPipeline
from piighost.placeholder import (
    AnyPlaceholderFactory,
    LabelCounterPlaceholderFactory,
    LabelHashPlaceholderFactory,
    LabelPlaceholderFactory,
    MaskPlaceholderFactory,
    RedactPlaceholderFactory,
)

TEXT = "Contact Emma at emma@example.com."
DETECTOR = ExactMatchDetector({"Emma": "PERSON", "emma@example.com": "EMAIL"})

FACTORIES: dict[str, AnyPlaceholderFactory] = {
    "redact": RedactPlaceholderFactory(),
    "label": LabelPlaceholderFactory(),
    "label counter": LabelCounterPlaceholderFactory(),
    "label hash": LabelHashPlaceholderFactory(),
    "mask": MaskPlaceholderFactory(),
}


async def main() -> None:
    """Anonymize one text with each placeholder factory and print the result."""
    print("text:", TEXT, "\n")

    for name, factory in FACTORIES.items():
        pipeline = AnonymizationPipeline(
            DETECTOR, ExactEntityLinker(), Anonymizer(factory)
        )
        result = await pipeline.anonymize(TEXT)
        print(f"{name:>13}: {result.text}")


if __name__ == "__main__":
    asyncio.run(main())
