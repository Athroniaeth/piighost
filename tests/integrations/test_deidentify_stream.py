"""Streaming deanonymization on the shared TextDeidentifier.

Drives deanonymize_stream with a real local ThreadAnonymizationPipeline and an
ExactMatchDetector, feeding an async source of chunks, no framework needed.
"""

from collections.abc import AsyncIterator

import pytest

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import (
    LabelCounterPlaceholderFactory,
    PreservesLabeledIdentityOpaque,
)
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.exceptions import InventedPlaceholderError
from piighost.integrations._deidentify import TextDeidentifier
from piighost.integrations.langchain.strategy import InventedPlaceholderStrategy
from piighost.pipeline import ThreadAnonymizationPipeline


def _pipeline() -> ThreadAnonymizationPipeline[PreservesLabeledIdentityOpaque]:
    """A thread pipeline over a counter factory and in-memory backend."""
    detector = ExactMatchDetector({"Patrick": "PERSON"})
    linker = ExactEntityLinker()
    factory = LabelCounterPlaceholderFactory()
    anonymizer = Anonymizer(factory)
    memory = InMemoryConversationMemory()
    return ThreadAnonymizationPipeline(detector, linker, anonymizer, memory)


async def _chunks(*parts: str) -> AsyncIterator[str]:
    """Yield each part as a streamed chunk."""
    for part in parts:
        yield part


def _deid(
    strategy: InventedPlaceholderStrategy = InventedPlaceholderStrategy.RAISE,
) -> TextDeidentifier:
    return TextDeidentifier(_pipeline(), strategy)


async def _collect(source: AsyncIterator[str]) -> str:
    return "".join([chunk async for chunk in source])


async def test_token_split_across_chunks_is_restored() -> None:
    """A token split over two chunks is reassembled and restored to its value."""
    deid = _deid()
    await deid.anonymize("Patrick", "t1")  # prime <<PERSON:1>> -> Patrick
    out = await _collect(deid.deanonymize_stream(_chunks("Hi <<PER", "SON:1>>!"), "t1"))
    assert out == "Hi Patrick!"


async def test_literal_text_streams_through() -> None:
    """Text with no token streams through unchanged."""
    deid = _deid()
    out = await _collect(deid.deanonymize_stream(_chunks("hello ", "world"), "t1"))
    assert out == "hello world"


async def test_trailing_incomplete_token_is_flushed() -> None:
    """A stream ending inside an unclosed token flushes the fragment, no loss."""
    deid = _deid()
    out = await _collect(deid.deanonymize_stream(_chunks("end <<PER"), "t1"))
    assert out == "end <<PER"


async def test_invented_token_is_dropped() -> None:
    """Under DROP, a token the pipeline never issued is removed from the stream."""
    deid = _deid(InventedPlaceholderStrategy.DROP)
    out = await _collect(deid.deanonymize_stream(_chunks("a <<GHOST:9>> b"), "t1"))
    assert out == "a  b"


async def test_invented_token_raises() -> None:
    """Under RAISE, a token the pipeline never issued is refused."""
    deid = _deid(InventedPlaceholderStrategy.RAISE)
    with pytest.raises(InventedPlaceholderError):
        await _collect(deid.deanonymize_stream(_chunks("<<GHOST:9>>"), "t1"))
