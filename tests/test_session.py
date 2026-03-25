"""Tests for AnonymizationSession (synchronous session wrapper)."""

import pytest

from piighost.anonymizer.anonymizer import Anonymizer
from piighost.anonymizer.models import (
    Entity,
    IrreversibleAnonymizationError,
)
from piighost.anonymizer.placeholder import RedactPlaceholderFactory
from piighost.registry import PlaceholderRegistry
from piighost.session import AnonymizationSession

from tests.fakes import FakeDetector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_anonymizer(*entities: Entity) -> Anonymizer:
    return Anonymizer(detector=FakeDetector(list(entities)))


PATRICK = Entity(text="Patrick", label="PERSON", start=0, end=7, score=0.9)
PARIS = Entity(text="Paris", label="LOCATION", start=18, end=23, score=0.85)


@pytest.fixture()
def session() -> AnonymizationSession:
    """Session with a fake detector for Patrick + Paris."""
    return AnonymizationSession(anonymizer=_make_anonymizer(PATRICK, PARIS))


# ---------------------------------------------------------------------------
# Anonymize
# ---------------------------------------------------------------------------


class TestAnonymize:
    """Tests for the synchronous anonymize method."""

    def test_anonymize_registers_placeholders(
        self, session: AnonymizationSession
    ) -> None:
        result = session.anonymize("Patrick habite à Paris.")

        assert "<<PERSON_1>>" in result.anonymized_text
        assert "<<LOCATION_1>>" in result.anonymized_text
        assert len(session.registry) == 2

    def test_no_pii_skips_registration(self) -> None:
        s = AnonymizationSession(anonymizer=_make_anonymizer())
        result = s.anonymize("Rien de spécial.")

        assert result.anonymized_text == "Rien de spécial."
        assert len(s.registry) == 0

    def test_active_labels_forwarded(self) -> None:
        """active_labels parameter is passed through to the detector."""
        s = AnonymizationSession(anonymizer=_make_anonymizer(PATRICK))
        result = s.anonymize("Patrick est ici.", active_labels=["PERSON"])
        assert "<<PERSON_1>>" in result.anonymized_text


# ---------------------------------------------------------------------------
# Deanonymize / Reanonymize
# ---------------------------------------------------------------------------


class TestDeanonymizeReanonymize:
    """Tests for deanonymize_text and reanonymize_text."""

    def test_deanonymize_text(self, session: AnonymizationSession) -> None:
        session.anonymize("Patrick habite à Paris.")

        restored = session.deanonymize_text("<<PERSON_1>> habite à <<LOCATION_1>>.")
        assert restored == "Patrick habite à Paris."

    def test_reanonymize_text(self, session: AnonymizationSession) -> None:
        session.anonymize("Patrick habite à Paris.")

        reanon = session.reanonymize_text("Résultat pour Patrick à Paris")
        assert "<<PERSON_1>>" in reanon
        assert "<<LOCATION_1>>" in reanon
        assert "Patrick" not in reanon
        assert "Paris" not in reanon

    def test_deanonymize_on_derived_text(self, session: AnonymizationSession) -> None:
        """deanonymize_text works on LLM-generated text, not just exact output."""
        session.anonymize("Patrick habite à Paris.")

        llm_output = "J'ai envoyé un email à <<PERSON_1>> concernant <<LOCATION_1>>."
        restored = session.deanonymize_text(llm_output)
        assert restored == "J'ai envoyé un email à Patrick concernant Paris."

    def test_roundtrip_deanonymize_reanonymize(
        self, session: AnonymizationSession
    ) -> None:
        """deanonymize then reanonymize gives back the anonymised form."""
        session.anonymize("Patrick habite à Paris.")

        anonymized = "<<PERSON_1>> habite à <<LOCATION_1>>."
        roundtrip = session.reanonymize_text(session.deanonymize_text(anonymized))
        assert roundtrip == anonymized


# ---------------------------------------------------------------------------
# Reversibility check
# ---------------------------------------------------------------------------


class TestReversibilityCheck:
    """Tests for _check_reversible via deanonymize/reanonymize."""

    def test_irreversible_raises_on_deanonymize(self) -> None:
        session = AnonymizationSession(
            anonymizer=Anonymizer(
                detector=FakeDetector([PATRICK]),
                placeholder_factory=RedactPlaceholderFactory(),
            )
        )
        session.anonymize("Patrick est ici.")

        with pytest.raises(IrreversibleAnonymizationError):
            session.deanonymize_text("[REDACTED] est ici.")

    def test_irreversible_raises_on_reanonymize(self) -> None:
        session = AnonymizationSession(
            anonymizer=Anonymizer(
                detector=FakeDetector([PATRICK]),
                placeholder_factory=RedactPlaceholderFactory(),
            )
        )
        session.anonymize("Patrick est ici.")

        with pytest.raises(IrreversibleAnonymizationError):
            session.reanonymize_text("Patrick est ici.")


# ---------------------------------------------------------------------------
# Registry access and sharing
# ---------------------------------------------------------------------------


class TestRegistryAccess:
    """Tests for the registry property, shared registries, and reset."""

    def test_registry_property(self, session: AnonymizationSession) -> None:
        assert isinstance(session.registry, PlaceholderRegistry)

    def test_shared_registry(self) -> None:
        """Multiple sessions can share a single registry."""
        shared = PlaceholderRegistry()
        anonymizer = _make_anonymizer(PATRICK, PARIS)
        s1 = AnonymizationSession(anonymizer=anonymizer, registry=shared)
        s2 = AnonymizationSession(anonymizer=anonymizer, registry=shared)

        s1.anonymize("Patrick habite à Paris.")

        # s2 sees s1's placeholders via the shared registry
        assert s2.deanonymize_text("<<PERSON_1>>") == "Patrick"

    def test_reset_clears_state(self, session: AnonymizationSession) -> None:
        session.anonymize("Patrick habite à Paris.")
        assert len(session.registry) == 2

        session.reset()
        assert len(session.registry) == 0

    def test_reset_preserves_shared_registry_reference(self) -> None:
        """reset() clears the shared registry in place, not replaces it."""
        shared = PlaceholderRegistry()
        anonymizer = _make_anonymizer(PATRICK, PARIS)
        s1 = AnonymizationSession(anonymizer=anonymizer, registry=shared)
        s2 = AnonymizationSession(anonymizer=anonymizer, registry=shared)

        s1.anonymize("Patrick habite à Paris.")
        assert len(shared) == 2

        s1.reset()
        # s1 still references the same shared object
        assert s1.registry is shared
        # shared is cleared (both sessions see it)
        assert len(shared) == 0
        assert len(s2.registry) == 0
