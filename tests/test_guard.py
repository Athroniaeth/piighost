"""Tests for the guard-rail stage and its pipeline integration."""

from __future__ import annotations

import pytest

from piighost.anonymizer import Anonymizer
from piighost.detector.base import ExactMatchDetector, RegexDetector
from piighost.exceptions import PIIRemainingError
from piighost.guard import DetectorGuardRail, DisabledGuardRail, filter_token_overlaps
from piighost.models import Detection, Span
from piighost.pipeline import AnonymizationPipeline
from piighost.placeholder import LabelCounterPlaceholderFactory


# ---------------------------------------------------------------------------
# DisabledGuardRail
# ---------------------------------------------------------------------------


class TestDisabledGuardRail:
    """DisabledGuardRail is a passthrough by design."""

    async def test_passes_arbitrary_text(self) -> None:
        guard = DisabledGuardRail()
        await guard.check("Patrick lives in Paris.")
        await guard.check("<<PERSON:1>> lives in <<LOCATION:1>>.")
        await guard.check("")


# ---------------------------------------------------------------------------
# DetectorGuardRail
# ---------------------------------------------------------------------------


class TestDetectorGuardRail:
    """DetectorGuardRail re-runs a detector on the anonymized output."""

    async def test_passes_when_no_residual_detections(self) -> None:
        guard = DetectorGuardRail(
            detector=RegexDetector(patterns={"EMAIL": r"\S+@\S+"}),
        )
        await guard.check("Hello <<PERSON:1>>, no email here.")

    async def test_raises_when_residual_pii_present(self) -> None:
        guard = DetectorGuardRail(
            detector=RegexDetector(patterns={"EMAIL": r"\S+@\S+"}),
        )
        with pytest.raises(PIIRemainingError) as exc_info:
            await guard.check("Hello <<PERSON:1>>, contact me at user@example.com.")

        err = exc_info.value
        assert err.detections, "PIIRemainingError should carry the residual detections"
        assert err.detections[0].label == "EMAIL"
        assert err.detections[0].text == "user@example.com."

    async def test_residual_detections_count_in_message(self) -> None:
        guard = DetectorGuardRail(
            detector=RegexDetector(patterns={"DIGITS": r"\d+"}),
        )
        with pytest.raises(PIIRemainingError) as exc_info:
            await guard.check("ref 123 and ref 456")
        assert "2 residual" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Pipeline integration
# ---------------------------------------------------------------------------


def _pipeline_with_guard(
    primary_detector: ExactMatchDetector,
    guard_detector: RegexDetector,
) -> AnonymizationPipeline:
    return AnonymizationPipeline(
        detector=primary_detector,
        anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
        guard_rail=DetectorGuardRail(detector=guard_detector),
    )


class TestPipelineIntegration:
    """A guard rail wired into the pipeline runs after anonymization."""

    async def test_default_guard_is_noop(self) -> None:
        """Without a guard_rail argument, anonymize behaves as before."""
        pipeline = AnonymizationPipeline(
            detector=ExactMatchDetector([("Patrick", "PERSON")]),
            anonymizer=Anonymizer(LabelCounterPlaceholderFactory()),
        )
        anonymized, _ = await pipeline.anonymize("Patrick lives here.")
        assert anonymized == "<<PERSON:1>> lives here."

    async def test_passes_when_anonymization_is_complete(self) -> None:
        """Primary detector covers all PII the guard would otherwise raise on."""
        pipeline = _pipeline_with_guard(
            primary_detector=ExactMatchDetector(
                [("Patrick", "PERSON"), ("user@example.com", "EMAIL")],
            ),
            guard_detector=RegexDetector(patterns={"EMAIL": r"\S+@\S+"}),
        )
        anonymized, _ = await pipeline.anonymize(
            "Patrick lives here, contact user@example.com."
        )
        assert "user@example.com" not in anonymized

    async def test_raises_when_primary_detector_misses_pii(self) -> None:
        """Guard catches what the primary detector did not anonymize."""
        pipeline = _pipeline_with_guard(
            # Primary only knows about Patrick, misses the email
            primary_detector=ExactMatchDetector([("Patrick", "PERSON")]),
            guard_detector=RegexDetector(patterns={"EMAIL": r"\S+@\S+"}),
        )
        with pytest.raises(PIIRemainingError) as exc_info:
            await pipeline.anonymize("Patrick lives here, contact user@example.com.")
        residual_labels = [d.label for d in exc_info.value.detections]
        assert "EMAIL" in residual_labels

    async def test_no_mapping_cached_when_guard_raises(self) -> None:
        """A raised guard short-circuits before the cache write so that
        subsequent deanonymize() calls cannot return tainted text."""
        from piighost.exceptions import CacheMissError

        pipeline = _pipeline_with_guard(
            primary_detector=ExactMatchDetector([("Patrick", "PERSON")]),
            guard_detector=RegexDetector(patterns={"EMAIL": r"\S+@\S+"}),
        )
        with pytest.raises(PIIRemainingError):
            await pipeline.anonymize("Patrick lives here, contact user@example.com.")

        # The anonymized text the pipeline tried to produce is not in
        # the cache, so deanonymize must fail.
        partial_anonymized = "<<PERSON:1>> lives here, contact user@example.com."
        with pytest.raises(CacheMissError):
            await pipeline.deanonymize(partial_anonymized)


# ---------------------------------------------------------------------------
# Token-aware guard rail
# ---------------------------------------------------------------------------


async def test_detector_guard_ignores_known_tokens():
    # A NER-ish detector that would flag the fake name used as a token.
    detector = ExactMatchDetector([("Jean Dupont", "PERSON")])
    guard = DetectorGuardRail(detector=detector)
    # The faker token IS the placeholder: must not raise.
    await guard.check("Bonjour Jean Dupont", tokens=["Jean Dupont"])


async def test_detector_guard_still_flags_real_residual_pii():
    detector = ExactMatchDetector([("Jean Dupont", "PERSON"), ("Alice", "PERSON")])
    guard = DetectorGuardRail(detector=detector)
    with pytest.raises(PIIRemainingError):
        await guard.check("Jean Dupont et Alice", tokens=["Jean Dupont"])


def test_filter_token_overlaps_drops_overlapping_detections():
    text = "Hello <<PERSON:1>> world"
    inside = Detection(
        text="PERSON", label="PERSON", position=Span(8, 14), confidence=1.0
    )
    outside = Detection(
        text="world", label="PERSON", position=Span(19, 24), confidence=1.0
    )
    kept = filter_token_overlaps([inside, outside], text, ["<<PERSON:1>>"])
    assert kept == [outside]


async def test_detector_guard_keeps_detection_containing_token_plus_real_pii():
    detector = ExactMatchDetector([("Jean Dupont Smith", "PERSON")])
    guard = DetectorGuardRail(detector=detector)
    # The detection spans the token plus adjacent real PII ("Smith"):
    # the uncovered residue contains word characters, so the guard raises.
    with pytest.raises(PIIRemainingError):
        await guard.check("Jean Dupont Smith called", tokens=["Jean Dupont"])


async def test_detector_guard_drops_detection_with_only_punctuation_residue():
    detector = ExactMatchDetector([("Jean Dupont", "PERSON")])
    guard = DetectorGuardRail(detector=detector)
    # Detection spans "Jean Dupont" exactly; residue is empty: exempt.
    await guard.check("Hello Jean Dupont.", tokens=["Jean Dupont"])


def test_filter_token_overlaps_requires_token_sequence_not_str():
    with pytest.raises(TypeError):
        filter_token_overlaps([], "text", "Jean")


def test_filter_token_overlaps_does_not_exempt_superstring_pii():
    # "Jean Duponte" is real PII, not the token "Jean Dupont": the
    # boundary-anchored match must not treat it as a token occurrence.
    text = "Jean Duponte called"
    d = Detection(
        text="Jean Duponte", label="PERSON", position=Span(0, 12), confidence=1.0
    )
    kept = filter_token_overlaps([d], text, ["Jean Dupont"])
    assert kept == [d]


def test_filter_token_overlaps_handles_multiple_occurrences():
    text = "<<PERSON:1>> met <<PERSON:1>>"
    d1 = Detection(text="PERSON", label="PERSON", position=Span(2, 8), confidence=1.0)
    d2 = Detection(text="PERSON", label="PERSON", position=Span(19, 25), confidence=1.0)
    kept = filter_token_overlaps([d1, d2], text, ["<<PERSON:1>>"])
    assert kept == []


def test_filter_token_overlaps_empty_tokens_keeps_everything():
    d = Detection(text="Alice", label="PERSON", position=Span(0, 5), confidence=1.0)
    assert filter_token_overlaps([d], "Alice", []) == [d]
