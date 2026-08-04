"""Tests for the thread-pipeline port and its token-grammar recognizer."""

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import (
    LabelCounterPlaceholderFactory,
    MaskPlaceholderFactory,
)
from piighost.components.placeholder.base import BaseDelimitedPlaceholderFactory
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.pipeline import AnyThreadPipeline, ThreadAnonymizationPipeline


def _pipeline(factory: object) -> ThreadAnonymizationPipeline:
    """Build a thread pipeline over the given placeholder factory."""
    return ThreadAnonymizationPipeline(
        ExactMatchDetector({"Emma": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(factory),
        InMemoryConversationMemory(),
    )


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """ThreadAnonymizationPipeline is an AnyThreadPipeline."""
        pipeline = _pipeline(LabelCounterPlaceholderFactory())
        assert isinstance(pipeline, AnyThreadPipeline)


class TestRecognizer:
    def test_a_delimited_factory_is_its_own_recognizer(self) -> None:
        """A delimited factory is returned as the recognizer."""
        factory = LabelCounterPlaceholderFactory()
        pipeline = _pipeline(factory)
        assert pipeline.recognizer is factory
        assert isinstance(pipeline.recognizer, BaseDelimitedPlaceholderFactory)

    def test_a_mask_factory_has_no_recognizer(self) -> None:
        """A non-delimited factory yields no recognizer."""
        pipeline = _pipeline(MaskPlaceholderFactory())
        assert pipeline.recognizer is None
