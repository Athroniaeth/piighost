from collections import defaultdict
from collections.abc import Mapping

from piighost.components.placeholder import AnyPlaceholderFactory
from piighost.components.placeholder.tags import PreservesLabeledIdentityOpaque
from piighost.models import Entity


class BracketPlaceholderFactory(AnyPlaceholderFactory[PreservesLabeledIdentityOpaque]):
    """Generate tokens in the format [PERSON:1], [LOCATION:2], etc."""

    def create(
        self, entities: list[Entity]
    ) -> Mapping[Entity, PreservesLabeledIdentityOpaque]:
        tokens: dict[Entity, PreservesLabeledIdentityOpaque] = {}
        counters: dict[str, int] = defaultdict(int)

        for entity in entities:
            counters[entity.label] += 1
            inner = f"{entity.label}:{counters[entity.label]}"
            tokens[entity] = PreservesLabeledIdentityOpaque(f"[{inner}]")

        return tokens


# Not shown: the factory, put to work.
import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import AnonymizationPipeline

pipeline = AnonymizationPipeline(
    ExactMatchDetector({"Patrick": "PERSON", "office@example.com": "EMAIL"}),
    anonymizer=Anonymizer(BracketPlaceholderFactory()),
)
text = asyncio.run(pipeline.anonymize("Patrick writes from office@example.com.")).text
print(text)
