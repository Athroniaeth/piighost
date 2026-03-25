"""Tests for AnonymizationPipeline with PlaceholderRegistry composition."""

import asyncio

import pytest

from piighost.anonymizer.anonymizer import Anonymizer
from piighost.anonymizer.models import (
    Entity,
    IrreversibleAnonymizationError,
)
from piighost.anonymizer.placeholder import (
    RedactPlaceholderFactory,
)
from piighost.pipeline import AnonymizationPipeline
from piighost.registry import PlaceholderRegistry

from tests.fakes import FakeDetector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_anonymizer(*entities: Entity) -> Anonymizer:
    return Anonymizer(detector=FakeDetector(list(entities)))


PATRICK = Entity(text="Patrick", label="PERSON", start=0, end=7, score=0.9)
PARIS = Entity(text="Paris", label="LOCATION", start=18, end=23, score=0.85)


@pytest.fixture()
def pipeline() -> AnonymizationPipeline:
    """Pipeline with a fake detector for Patrick + Paris."""
    return AnonymizationPipeline(anonymizer=_make_anonymizer(PATRICK, PARIS))


# ---------------------------------------------------------------------------
# Anonymize
# ---------------------------------------------------------------------------


class TestAnonymize:
    """Tests for the async anonymize method."""

    def test_anonymize_registers_placeholders(
        self, pipeline: AnonymizationPipeline
    ) -> None:
        result = asyncio.run(pipeline.anonymize("Patrick habite à Paris."))

        assert "<<PERSON_1>>" in result.anonymized_text
        assert "<<LOCATION_1>>" in result.anonymized_text
        assert len(pipeline.registry) == 2

    def test_cache_hit_returns_same_result(
        self, pipeline: AnonymizationPipeline
    ) -> None:
        async def _run() -> None:
            text = "Patrick habite à Paris."
            r1 = await pipeline.anonymize(text)
            r2 = await pipeline.anonymize(text)
            assert r1 is r2

        asyncio.run(_run())

    def test_no_pii_skips_store(self) -> None:
        p = AnonymizationPipeline(anonymizer=_make_anonymizer())
        result = asyncio.run(p.anonymize("Rien de spécial."))

        assert result.anonymized_text == "Rien de spécial."
        assert len(p.registry) == 0


# ---------------------------------------------------------------------------
# Deanonymize / Reanonymize via registry
# ---------------------------------------------------------------------------


class TestDeanonymizeReanonymize:
    """Tests for deanonymize_text and reanonymize_text."""

    def test_deanonymize_text(self, pipeline: AnonymizationPipeline) -> None:
        asyncio.run(pipeline.anonymize("Patrick habite à Paris."))

        restored = pipeline.deanonymize_text("<<PERSON_1>> habite à <<LOCATION_1>>.")
        assert restored == "Patrick habite à Paris."

    def test_reanonymize_text(self, pipeline: AnonymizationPipeline) -> None:
        asyncio.run(pipeline.anonymize("Patrick habite à Paris."))

        reanon = pipeline.reanonymize_text("Résultat pour Patrick à Paris")
        assert "<<PERSON_1>>" in reanon
        assert "<<LOCATION_1>>" in reanon
        assert "Patrick" not in reanon
        assert "Paris" not in reanon

    def test_deanonymize_on_derived_text(self, pipeline: AnonymizationPipeline) -> None:
        """deanonymize_text works on LLM-generated text, not just exact output."""
        asyncio.run(pipeline.anonymize("Patrick habite à Paris."))

        llm_output = "J'ai envoyé un email à <<PERSON_1>> concernant <<LOCATION_1>>."
        restored = pipeline.deanonymize_text(llm_output)
        assert restored == "J'ai envoyé un email à Patrick concernant Paris."


# ---------------------------------------------------------------------------
# Reversibility check
# ---------------------------------------------------------------------------


class TestReversibilityCheck:
    """Tests for _check_reversible via deanonymize/reanonymize."""

    def test_irreversible_raises_on_deanonymize(self) -> None:
        pipeline = AnonymizationPipeline(
            anonymizer=Anonymizer(
                detector=FakeDetector([PATRICK]),
                placeholder_factory=RedactPlaceholderFactory(),
            )
        )
        asyncio.run(pipeline.anonymize("Patrick est ici."))

        with pytest.raises(IrreversibleAnonymizationError):
            pipeline.deanonymize_text("[REDACTED] est ici.")

    def test_irreversible_raises_on_reanonymize(self) -> None:
        pipeline = AnonymizationPipeline(
            anonymizer=Anonymizer(
                detector=FakeDetector([PATRICK]),
                placeholder_factory=RedactPlaceholderFactory(),
            )
        )
        asyncio.run(pipeline.anonymize("Patrick est ici."))

        with pytest.raises(IrreversibleAnonymizationError):
            pipeline.reanonymize_text("Patrick est ici.")


# ---------------------------------------------------------------------------
# Registry access
# ---------------------------------------------------------------------------


class TestRegistryAccess:
    """Tests for the registry property and shared registries."""

    def test_registry_property(self, pipeline: AnonymizationPipeline) -> None:
        assert isinstance(pipeline.registry, PlaceholderRegistry)

    def test_shared_registry(self) -> None:
        """Multiple pipelines can share a single registry."""
        shared = PlaceholderRegistry()
        anonymizer = _make_anonymizer(PATRICK, PARIS)
        p1 = AnonymizationPipeline(anonymizer=anonymizer, registry=shared)
        p2 = AnonymizationPipeline(anonymizer=anonymizer, registry=shared)

        asyncio.run(p1.anonymize("Patrick habite à Paris."))

        # p2 sees p1's placeholders via the shared registry
        assert p2.deanonymize_text("<<PERSON_1>>") == "Patrick"

    def test_pipeline_reset(self) -> None:
        """Pipeline.reset() clears session state."""
        pipeline = AnonymizationPipeline(anonymizer=_make_anonymizer(PATRICK, PARIS))
        asyncio.run(pipeline.anonymize("Patrick habite à Paris."))
        assert len(pipeline.registry) == 2

        pipeline.reset()
        assert len(pipeline.registry) == 0
