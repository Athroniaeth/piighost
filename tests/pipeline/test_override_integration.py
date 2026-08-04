"""Integration tests for the override stage in both pipelines."""

import pytest

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.guard import DetectorGuardRail
from piighost.components.linker import ExactEntityLinker
from piighost.components.override import BlacklistStrategy, DetectionOverride
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.exceptions import PIIRemainingError
from piighost.pipeline import AnonymizationPipeline


def _pipeline(
    detector: ExactMatchDetector,
    override: DetectionOverride,
    guard: DetectorGuardRail | None = None,
) -> AnonymizationPipeline:
    """Build a base pipeline with an override and an optional guard."""
    return AnonymizationPipeline(
        detector,
        ExactEntityLinker(),
        Anonymizer(LabelCounterPlaceholderFactory()),
        guard=guard,
        override=override,
    )


class TestBasePipelineOverride:
    async def test_whitelist_forces_a_value_the_detector_missed(self) -> None:
        """A whitelisted value is anonymized though the detector never saw it."""
        override = DetectionOverride(whitelist=ExactMatchDetector({"Acme": "ORG"}))
        pipeline = _pipeline(ExactMatchDetector({}), override)
        result = await pipeline.anonymize("Acme rocks")
        assert result.text == "<<ORG:1>> rocks"

    async def test_blacklist_keeps_a_false_positive_in_clear(self) -> None:
        """A blacklisted value the detector flags stays in clear."""
        override = DetectionOverride(
            blacklist=ExactMatchDetector({"Paris": "LOCATION"})
        )
        pipeline = _pipeline(ExactMatchDetector({"Paris": "LOCATION"}), override)
        result = await pipeline.anonymize("Visit Paris")
        assert result.text == "Visit Paris"

    async def test_blacklisted_value_does_not_trip_the_guard(self) -> None:
        """A guard that knows the blacklisted value exempts it, by design."""
        override = DetectionOverride(
            blacklist=ExactMatchDetector({"Paris": "LOCATION"}),
            blacklist_strategy=BlacklistStrategy.VALUE,
        )
        guard = DetectorGuardRail(ExactMatchDetector({"Paris": "LOCATION"}))
        pipeline = _pipeline(ExactMatchDetector({"Emma": "PERSON"}), override, guard)
        result = await pipeline.anonymize("Emma visits Paris")
        assert result.text == "<<PERSON:1>> visits Paris"

    async def test_a_real_leak_still_trips_the_guard(self) -> None:
        """The exemption covers the blacklist only, other leaks still refuse."""
        override = DetectionOverride(
            blacklist=ExactMatchDetector({"Paris": "LOCATION"})
        )
        guard = DetectorGuardRail(ExactMatchDetector({"leak@x.com": "EMAIL"}))
        pipeline = _pipeline(ExactMatchDetector({"Emma": "PERSON"}), override, guard)
        with pytest.raises(PIIRemainingError):
            await pipeline.anonymize("Emma wrote leak@x.com")
