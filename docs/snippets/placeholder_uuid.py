import uuid
from collections.abc import Mapping

from piighost.components.placeholder import AnyPlaceholderFactory
from piighost.components.placeholder.tags import PreservesIdentityOnly
from piighost.models import Entity


class UUIDPlaceholderFactory(AnyPlaceholderFactory[PreservesIdentityOnly]):
    """Generate opaque delimited ids, e.g. <<a3f21b4c>>, no label revealed."""

    def create(self, entities: list[Entity]) -> Mapping[Entity, PreservesIdentityOnly]:
        tokens: dict[Entity, PreservesIdentityOnly] = {}
        seen: dict[str, PreservesIdentityOnly] = {}  # canonical value -> token

        for entity in entities:
            canonical = entity.text.lower()
            if canonical not in seen:
                seen[canonical] = PreservesIdentityOnly(f"<<{uuid.uuid4().hex[:8]}>>")
            tokens[entity] = seen[canonical]

        return tokens


# Not shown: the factory, put to work.
import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import AnonymizationPipeline

pipeline = AnonymizationPipeline(
    ExactMatchDetector({"Patrick": "PERSON", "office@example.com": "EMAIL"}),
    anonymizer=Anonymizer(UUIDPlaceholderFactory()),
)
text = asyncio.run(pipeline.anonymize("Patrick writes from office@example.com.")).text
print("<<" in text and "Patrick" not in text)
