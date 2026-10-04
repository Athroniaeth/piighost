import asyncio

# isort: split
# --8<-- [start:handle_detector]
import re

from piighost.models import Detection, Span


class HandleDetector:
    """Detect @handles as USERNAME."""

    async def detect(self, text: str) -> list[Detection]:
        detections: list[Detection] = []
        for match in re.finditer(r"@\w+", text):
            span = Span(match.start(), match.end())
            detections.append(
                Detection(
                    span=span,
                    text=match.group(),
                    label="USERNAME",
                    confidence=1.0,
                )
            )
        return detections


# --8<-- [end:handle_detector]


# isort: split
# --8<-- [start:use_detector]
from piighost.pipeline import AnonymizationPipeline

detector = HandleDetector()
pipeline = AnonymizationPipeline(detector)
# --8<-- [end:use_detector]


# isort: split
# --8<-- [start:longest_resolver]
from piighost.components.overlap_resolver.base import BaseOverlapResolver
from piighost.models import Detection


class LongestOverlapResolver(BaseOverlapResolver):
    """Keep the longest detection in each overlap group."""

    def _reduce(self, conflicting: list[Detection]) -> list[Detection]:
        return [max(conflicting, key=lambda d: d.span.length)]


# --8<-- [end:longest_resolver]


# isort: split
# --8<-- [start:whole_word_expander]
from collections.abc import Iterable

from piighost.components.expander.base import BaseDetectionExpander
from piighost.models import Detection


class WholeWordExpander(BaseDetectionExpander):
    """Find whole-word repeats of a detected value."""

    def _find_occurrences(self, text: str, detection: Detection) -> Iterable[Span]:
        pattern = re.compile(rf"\b{re.escape(detection.text)}\b")
        return [Span(m.start(), m.end()) for m in pattern.finditer(text)]


# --8<-- [end:whole_word_expander]


# isort: split
# --8<-- [start:case_sensitive_linker]
from collections.abc import Hashable

from piighost.components.linker.base import BaseEntityLinker
from piighost.models import Detection


class CaseSensitiveLinker(BaseEntityLinker):
    """Group detections that share an exact value and label."""

    def _key(self, detection: Detection) -> Hashable:
        return (detection.text, detection.label)


# --8<-- [end:case_sensitive_linker]


# isort: split
# --8<-- [start:bracket_factory]
from collections.abc import Mapping

from piighost.components.placeholder.base import AnyPlaceholderFactory
from piighost.components.placeholder.tags import PreservesLabel
from piighost.models import Entity


class BracketLabelFactory(AnyPlaceholderFactory[PreservesLabel]):
    """Emit [LABEL] for every entity, collapsing each label to one token."""

    def create(self, entities: list[Entity]) -> Mapping[Entity, PreservesLabel]:
        return {entity: PreservesLabel(f"[{entity.label}]") for entity in entities}


# --8<-- [end:bracket_factory]


# isort: split
# --8<-- [start:use_factory]
from piighost.components.anonymizer import Anonymizer

factory = BracketLabelFactory()
anonymizer = Anonymizer(factory)
# --8<-- [end:use_factory]


# isort: split
# --8<-- [start:at_sign_guard]
from piighost.components.guard.base import GuardVerdict


class AtSignGuard:
    """Flag any residual @ sign as leftover PII."""

    async def check(self, text: str) -> GuardVerdict:
        return GuardVerdict(flagged="@" in text)


# --8<-- [end:at_sign_guard]


# isort: split
# --8<-- [start:use_guard]
from piighost.pipeline import AnonymizationPipeline

guard = AtSignGuard()
pipeline = AnonymizationPipeline(detector, guard=guard)
# --8<-- [end:use_guard]


# isort: split
# --8<-- [start:assemble]
from piighost.components.anonymizer import Anonymizer
from piighost.components.entity_resolver import MergeEntityResolver
from piighost.pipeline import AnonymizationPipeline

pipeline = AnonymizationPipeline(
    HandleDetector(),
    anonymizer=Anonymizer(BracketLabelFactory()),
    entity_resolver=MergeEntityResolver(),
    guard=AtSignGuard(),
)
# --8<-- [end:assemble]


# Not shown: the examples above, put to work.
async def check() -> None:
    print((await pipeline.anonymize("@alice wrote to @bob.")).text)
    grouped = AnonymizationPipeline(
        HandleDetector(),
        linker=CaseSensitiveLinker(),
        overlap_resolver=LongestOverlapResolver(),
        expander=WholeWordExpander(),
    )
    print((await grouped.anonymize("@alice and @alice, then @bob.")).text)
    flagged = await AtSignGuard().check("left @carol")
    print(flagged.flagged)


asyncio.run(check())
