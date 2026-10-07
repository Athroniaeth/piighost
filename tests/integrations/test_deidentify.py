"""Tests for the shared text de-identification core used by the integrations."""

import pytest

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import (
    AnyPlaceholderFactory,
    LabelCounterPlaceholderFactory,
    LabelHashPlaceholderFactory,
    LabelPlaceholderFactory,
    MaskPlaceholderFactory,
    PreservesLabeledIdentityOpaque,
    RedactPlaceholderFactory,
)
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.exceptions import (
    InventedPlaceholderError,
    IrreversibleFactoryError,
    UnrecognizableFactoryError,
)
from piighost.integrations._deidentify import TextDeidentifier
from piighost.integrations.langchain.strategy import InventedPlaceholderStrategy
from piighost.pipeline import ThreadAnonymizationPipeline


def _pipeline() -> ThreadAnonymizationPipeline[PreservesLabeledIdentityOpaque]:
    """Build a thread pipeline over a counter factory and in-memory backend."""
    return ThreadAnonymizationPipeline(
        ExactMatchDetector({"Emma": "PERSON", "Liam": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(LabelCounterPlaceholderFactory()),
        InMemoryConversationMemory(),
    )


def _deidentifier(
    invented_strategy: InventedPlaceholderStrategy = InventedPlaceholderStrategy.RAISE,
) -> TextDeidentifier:
    """Build a de-identifier over a fresh in-memory thread pipeline."""
    return TextDeidentifier(_pipeline(), invented_strategy)


class TestAnonymize:
    async def test_replaces_pii_with_a_token(self) -> None:
        """anonymize returns the text with PII replaced by a stable token."""
        deid = _deidentifier()
        assert await deid.anonymize("Hello Emma", "t1") == "Hello <<PERSON:1>>"


class TestDeanonymize:
    async def test_round_trips_a_message(self) -> None:
        """deanonymize restores the values anonymize replaced in the thread."""
        deid = _deidentifier()
        anonymized = await deid.anonymize("Emma met Liam", "t1")
        assert await deid.deanonymize(anonymized, "t1") == "Emma met Liam"


class TestInventedStrategy:
    async def test_keep_leaves_an_invented_token(self) -> None:
        """KEEP passes a token the pipeline never issued through unchanged."""
        deid = _deidentifier(InventedPlaceholderStrategy.KEEP)
        assert await deid.deanonymize("hi <<PERSON:9>>", "t1") == "hi <<PERSON:9>>"

    async def test_drop_removes_an_invented_token(self) -> None:
        """DROP strips a token the pipeline never issued from the output."""
        deid = _deidentifier(InventedPlaceholderStrategy.DROP)
        assert await deid.deanonymize("hi <<PERSON:9>>", "t1") == "hi "

    async def test_raise_refuses_an_invented_token(self) -> None:
        """RAISE refuses output holding a token the pipeline never issued."""
        deid = _deidentifier(InventedPlaceholderStrategy.RAISE)
        with pytest.raises(InventedPlaceholderError):
            await deid.deanonymize("hi <<PERSON:9>>", "t1")


class TestConstruction:
    def test_a_pipeline_without_a_recognizer_is_refused(self) -> None:
        """A pipeline whose factory has no recognizable grammar fails fast."""
        pipeline = ThreadAnonymizationPipeline(
            ExactMatchDetector({"Emma": "PERSON"}),
            ExactEntityLinker(),
            Anonymizer(MaskPlaceholderFactory()),
            InMemoryConversationMemory(),
        )
        with pytest.raises(UnrecognizableFactoryError):
            # The mask factory has no recognizable grammar, so its tag violates
            # the IdentityT bound on purpose; the point is the runtime refusal.
            TextDeidentifier(pipeline)  # pyrefly: ignore[bad-specialization]

    @pytest.mark.parametrize(
        "factory", [RedactPlaceholderFactory(), LabelPlaceholderFactory()]
    )
    def test_a_factory_that_shares_tokens_is_refused(
        self, factory: AnyPlaceholderFactory
    ) -> None:
        """A delimited factory whose tokens can be shared is refused at runtime.

        Its grammar is recognizable, so only the identity check catches it. A
        pipeline built from a config file is untyped, so the type bound alone
        would let a redact factory restore one value into every <<REDACT>>.
        """
        pipeline = ThreadAnonymizationPipeline(
            ExactMatchDetector({"Emma": "PERSON"}),
            ExactEntityLinker(),
            Anonymizer(factory),
            InMemoryConversationMemory(),
        )
        with pytest.raises(IrreversibleFactoryError):
            TextDeidentifier(pipeline)  # pyrefly: ignore[bad-specialization]

    @pytest.mark.parametrize(
        "factory", [LabelCounterPlaceholderFactory(), LabelHashPlaceholderFactory()]
    )
    def test_a_reversible_factory_is_accepted(
        self, factory: AnyPlaceholderFactory
    ) -> None:
        """Counter and hash tokens identify each entity, so they pass."""
        pipeline = ThreadAnonymizationPipeline(
            ExactMatchDetector({"Emma": "PERSON"}),
            ExactEntityLinker(),
            Anonymizer(factory),
            InMemoryConversationMemory(),
        )
        TextDeidentifier(pipeline)  # pyrefly: ignore[bad-specialization]
