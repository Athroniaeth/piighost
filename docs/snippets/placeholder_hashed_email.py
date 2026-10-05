import hashlib
from collections.abc import Mapping

from piighost.components.placeholder import AnyPlaceholderFactory
from piighost.components.placeholder.tags import PreservesLabeledIdentityHashed
from piighost.models import Entity


class HashedEmailPlaceholderFactory(
    AnyPlaceholderFactory[PreservesLabeledIdentityHashed]
):
    """Generate realistic emails like a1b2c3d4@anonymized.local."""

    def create(
        self, entities: list[Entity]
    ) -> Mapping[Entity, PreservesLabeledIdentityHashed]:
        tokens: dict[Entity, PreservesLabeledIdentityHashed] = {}

        for entity in entities:
            digest = hashlib.sha256(entity.text.encode()).hexdigest()[:8]
            tokens[entity] = PreservesLabeledIdentityHashed(
                f"{digest}@anonymized.local"
            )

        return tokens


# Not shown: the factory, put to work.
import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import AnonymizationPipeline

pipeline = AnonymizationPipeline(
    ExactMatchDetector({"Patrick": "PERSON", "office@example.com": "EMAIL"}),
    anonymizer=Anonymizer(HashedEmailPlaceholderFactory()),
)
text = asyncio.run(pipeline.anonymize("Patrick writes from office@example.com.")).text
print(text)
