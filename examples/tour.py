# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost"]
#
# [tool.uv.sources]
# piighost = { path = "..", editable = true }
# ///
"""A tour of what piighost does: anonymize, style, guard, and hold a thread.

Every detector here is the ExactMatchDetector, which matches literal strings,
so the examples stay self-contained and need no model. Run with:
uv run examples/tour.py
"""

import asyncio

from piighost.anonymizer import Anonymizer
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.detector import ExactMatchDetector
from piighost.entity_resolver import MergeEntityResolver
from piighost.exceptions import PIIRemainingError
from piighost.expander import WordBoundaryExpander
from piighost.guard import DetectorGuardRail
from piighost.linker import ExactEntityLinker
from piighost.overlap_resolver import ConfidenceOverlapResolver
from piighost.pipeline import AnonymizationPipeline, ThreadAnonymizationPipeline
from piighost.placeholder import (
    AnyPlaceholderFactory,
    LabelCounterPlaceholderFactory,
    LabelHashPlaceholderFactory,
    LabelPlaceholderFactory,
    MaskPlaceholderFactory,
    RedactPlaceholderFactory,
)


async def basic() -> None:
    """Anonymize a text, then restore it from the token mapping."""
    ph_factory = LabelCounterPlaceholderFactory()
    pipeline = AnonymizationPipeline(
        ExactMatchDetector({"Emma": "PERSON", "Lyon": "LOCATION"}),
        ExactEntityLinker(),
        Anonymizer(ph_factory),
    )

    text = "Emma lives in Lyon."
    result = await pipeline.anonymize(text)

    print("  original:  ", text)
    print("  anonymized:", result.text)
    print("  restored:  ", pipeline.deanonymize(result.text, result.tokens))


async def placeholder_styles() -> None:
    """Run one text through each placeholder factory to compare token forms."""
    text = "Contact Emma at emma@example.com."
    detector = ExactMatchDetector({"Emma": "PERSON", "emma@example.com": "EMAIL"})

    factories: dict[str, AnyPlaceholderFactory] = {
        "redact": RedactPlaceholderFactory(),
        "label": LabelPlaceholderFactory(),
        "label counter": LabelCounterPlaceholderFactory(),
        "label hash": LabelHashPlaceholderFactory(),
        "mask": MaskPlaceholderFactory(),
    }

    for name, ph_factory in factories.items():
        pipeline = AnonymizationPipeline(
            detector, ExactEntityLinker(), Anonymizer(ph_factory)
        )
        result = await pipeline.anonymize(text)
        print(f"  {name:>13}: {result.text}")


async def every_stage() -> None:
    """Wire every optional stage; a value keeps one token across its occurrences."""
    ph_factory = LabelCounterPlaceholderFactory()
    pipeline = AnonymizationPipeline(
        ExactMatchDetector({"Emma": "PERSON", "Bob": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(ph_factory),
        overlap_resolver=ConfidenceOverlapResolver(),
        expander=WordBoundaryExpander(),
        entity_resolver=MergeEntityResolver(),
    )

    result = await pipeline.anonymize("Emma called Bob. Emma waited. Bob answered.")
    print("  ", result.text)


async def guard_rail() -> None:
    """A second detector guards the output for PII the pipeline missed."""
    ph_factory = RedactPlaceholderFactory()
    guard_detector = ExactMatchDetector({"bob@example.com": "EMAIL"})
    pipeline = AnonymizationPipeline(
        ExactMatchDetector({"alice@example.com": "EMAIL"}),
        ExactEntityLinker(),
        Anonymizer(ph_factory),
        guard=DetectorGuardRail(guard_detector),
    )

    clean = await pipeline.anonymize("Write to alice@example.com.")
    print("  clean:", clean.text)

    try:
        await pipeline.anonymize("Write to alice@example.com and bob@example.com.")
    except PIIRemainingError as error:
        print("  guard:", error)


async def thread() -> None:
    """Keep tokens stable across a thread, isolate threads, and forget one."""
    ph_factory = LabelCounterPlaceholderFactory()
    pipeline = ThreadAnonymizationPipeline(
        ExactMatchDetector({"Emma": "PERSON", "Liam": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(ph_factory),
        InMemoryConversationMemory(),
    )

    first = await pipeline.anonymize("Hi, I am Emma.", "chat-1")
    second = await pipeline.anonymize("Emma, meet Liam.", "chat-1")
    other = await pipeline.anonymize("Emma again.", "chat-2")
    print("  chat-1 message 1:", first.text)
    print("  chat-1 message 2:", second.text)
    print("  chat-2 message 1:", other.text)

    forgotten = await pipeline.forget_thread("chat-1")
    print(f"  forgot chat-1: {forgotten.messages} messages, {forgotten.detections} detections")


async def main() -> None:
    """Run every section of the tour in turn."""
    sections = {
        "Anonymize and restore": basic,
        "Placeholder styles": placeholder_styles,
        "Every stage, one token per value": every_stage,
        "Guard rail": guard_rail,
        "Thread: consistency, isolation, forget": thread,
    }

    for title, section in sections.items():
        print(f"\n== {title} ==")
        await section()


if __name__ == "__main__":
    asyncio.run(main())
