# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost"]
#
# [tool.uv.sources]
# piighost = { path = "..", editable = true }
# ///
"""Anonymize a whole conversation with the thread-aware pipeline.

Within a thread a value keeps one placeholder across every message, threads
stay isolated from each other, a message can be restored, and a thread can be
forgotten for the right to erasure. Each message's detections are also cached,
so resending a message skips detection. Run with:
uv run examples/thread_conversation.py
"""

import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.pipeline import ThreadAnonymizationPipeline
from piighost.components.placeholder import LabelCounterPlaceholderFactory


def _build_pipeline() -> ThreadAnonymizationPipeline:
    """Wire a thread pipeline over an in-memory conversation store."""
    ph_factory = LabelCounterPlaceholderFactory()
    return ThreadAnonymizationPipeline(
        ExactMatchDetector({"Emma": "PERSON", "Liam": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(ph_factory),
        InMemoryConversationMemory(),
    )


async def main() -> None:
    """Walk a conversation through the thread pipeline, then forget it."""
    pipeline = _build_pipeline()

    print("== one thread: a value keeps its token across messages ==")
    conversation = [
        "Hi, I am Emma.",
        "Emma, who is joining?",
        "My colleague Liam is joining.",
    ]
    for message in conversation:
        result = await pipeline.anonymize(message, "t1")
        print(f"  {message!r:32} -> {result.text!r}")

    print("\n== restore a reply ==")
    reply = await pipeline.anonymize("Thanks Emma and Liam.", "t1")
    print("  anonymized:", reply.text)
    print("  restored:  ", await pipeline.deanonymize(reply.text, "t1"))

    print("\n== another thread numbers from one, independently ==")
    other = await pipeline.anonymize("Emma again.", "t2")
    print("  t2:", other.text)

    print("\n== forget the thread ==")
    forgotten = await pipeline.forget_thread("t1")
    print(f"  dropped {forgotten.messages} messages, {forgotten.detections} detections")


if __name__ == "__main__":
    asyncio.run(main())
