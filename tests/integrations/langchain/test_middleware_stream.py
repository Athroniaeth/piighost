"""The LangChain middleware exposes streaming deanonymization for app loops."""

from collections.abc import AsyncIterator

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import (
    LabelCounterPlaceholderFactory,
    PreservesLabeledIdentityOpaque,
)
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.integrations.langchain.middleware import PIIAnonymizationMiddleware
from piighost.pipeline import ThreadAnonymizationPipeline


async def _chunks(*parts: str) -> AsyncIterator[str]:
    """Yield each part as a streamed chunk."""
    for part in parts:
        yield part


def _pipeline() -> ThreadAnonymizationPipeline[PreservesLabeledIdentityOpaque]:
    """A thread pipeline over a counter factory and in-memory backend."""
    detector = ExactMatchDetector({"Patrick": "PERSON"})
    linker = ExactEntityLinker()
    factory = LabelCounterPlaceholderFactory()
    anonymizer = Anonymizer(factory)
    memory = InMemoryConversationMemory()
    return ThreadAnonymizationPipeline(detector, linker, anonymizer, memory)


async def test_middleware_deanonymize_stream_restores_split_token() -> None:
    """The middleware restores a token split across chunks via its own pipeline."""
    pipeline = _pipeline()
    middleware = PIIAnonymizationMiddleware(pipeline)
    await pipeline.anonymize("Patrick", "t1")  # prime <<PERSON:1>> -> Patrick
    stream = middleware.deanonymize_stream(_chunks("Hi <<PER", "SON:1>>"), "t1")
    out = "".join([chunk async for chunk in stream])
    assert out == "Hi Patrick"
