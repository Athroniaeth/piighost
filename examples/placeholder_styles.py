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

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import (
    AnyPlaceholderFactory,
    LabelCounterPlaceholderFactory,
    LabelHashPlaceholderFactory,
    LabelPlaceholderFactory,
    MaskPlaceholderFactory,
    RedactPlaceholderFactory,
)
from piighost.pipeline import AnonymizationPipeline

text = "Contact Emma at emma@example.com."
detector = ExactMatchDetector({"Emma": "PERSON", "emma@example.com": "EMAIL"})

factories: dict[str, AnyPlaceholderFactory] = {
    "redact": RedactPlaceholderFactory(),
    "label": LabelPlaceholderFactory(),
    "label counter": LabelCounterPlaceholderFactory(),
    "label hash": LabelHashPlaceholderFactory(),
    "mask": MaskPlaceholderFactory(),
}


async def main() -> None:
    """Anonymize one text with each placeholder factory and print the result."""
    print("text:", text, "\n")

    for name, factory in factories.items():
        pipeline = AnonymizationPipeline(
            detector,
            ExactEntityLinker(),
            Anonymizer(factory),
        )
        result = await pipeline.anonymize(text)
        print(f"{name:>13}: {result.text}")


if __name__ == "__main__":
    asyncio.run(main())
