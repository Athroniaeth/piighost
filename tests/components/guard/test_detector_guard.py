"""Tests for the DetectorGuardRail."""

import pytest

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.guard import AnyGuardRail, DetectorGuardRail
from piighost.components.placeholder import (
    LabelCounterPlaceholderFactory,
    MaskPlaceholderFactory,
)
from piighost.exceptions import PIIRemainingError
from piighost.models import Detection, Span
from piighost.pipeline import AnonymizationPipeline


class _SpanDetector:
    """A detector tagging every occurrence of fixed substrings, like a span model.

    It tags whatever it is given, placeholders included, which is what a model
    such as GLiNER2 does when it reads <<PERSON:1>> as a person.
    """

    def __init__(self, *values: str) -> None:
        self.values = values

    async def detect(self, text: str) -> list[Detection]:
        detections = []

        for value in self.values:
            start = text.find(value)
            while start != -1:
                span = Span(start, start + len(value))
                detection = Detection(
                    span=span,
                    text=value,
                    label="PERSON",
                    confidence=0.9,
                )
                detections.append(detection)
                start = text.find(value, start + 1)
        return detections


def _custom_factory() -> LabelCounterPlaceholderFactory:
    """Build a counter factory emitting [[PERSON:1]] instead of <<PERSON:1>>."""
    return LabelCounterPlaceholderFactory(prefix="[[", suffix="]]")


PLACEHOLDER_ONLY: dict[str, tuple[str, str]] = {
    "counter token": ("Hello <<PERSON:1>>.", "<<PERSON:1>>"),
    "two tokens and a comma": (
        "Hi <<PERSON:1>>, <<PERSON:2>>!",
        "<<PERSON:1>>, <<PERSON:2>>",
    ),
    "hash token": ("Hi <<PERSON:a1b2c3d4>>.", "<<PERSON:a1b2c3d4>>"),
    "label-only token": ("Hi <<PERSON>>.", "<<PERSON>>"),
    "token and a stray letter": ("The <<PERSON:1>>s agreed.", "<<PERSON:1>>s"),
    "part of a token": ("Call <<PERSON:8>> now.", "<<PERSON:8>"),
}
"""Detections that hold only placeholders, by case: the text, the tagged span."""

RESIDUAL: dict[str, tuple[str, str]] = {
    "a leak next to a placeholder": ("Emma wrote to <<PERSON:1>>.", "Emma"),
    "a surname after a first-name token": (
        "<<PERSON:1>> Dubois signed.",
        "<<PERSON:1>> Dubois",
    ),
    "a partial leak between tokens": (
        "<<PERSON:1>> and Mme Dubois met <<PERSON:2>>.",
        "Mme Dubois",
    ),
    "a civility next to a token": ("Mme <<PERSON:3>> called.", "Mme <<PERSON:3>>"),
}
"""Detections that keep a value beside the placeholders: the text, the tagged span."""


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """DetectorGuardRail is an AnyGuardRail."""
        assert isinstance(DetectorGuardRail(ExactMatchDetector({})), AnyGuardRail)


class TestCheck:
    async def test_clean_text_is_not_flagged(self) -> None:
        """Text the detector finds no PII in returns an unflagged verdict."""
        guard = DetectorGuardRail(ExactMatchDetector({"Emma": "PERSON"}))
        verdict = await guard.check("nothing to see here")
        assert verdict.flagged is False
        assert verdict.detections == ()

    async def test_residual_pii_is_flagged(self) -> None:
        """PII the detector still finds flags the verdict."""
        guard = DetectorGuardRail(ExactMatchDetector({"Emma": "PERSON"}))
        verdict = await guard.check("Emma slipped through")
        assert verdict.flagged is True

    async def test_verdict_carries_the_residual_detections(self) -> None:
        """The verdict exposes what leaked."""
        guard = DetectorGuardRail(ExactMatchDetector({"Emma": "PERSON"}))
        verdict = await guard.check("Emma slipped through")
        assert [detection.text for detection in verdict.detections] == ["Emma"]

    async def test_synthetic_placeholders_are_not_flagged(self) -> None:
        """A detector for real PII does not match the synthetic placeholder form."""
        guard = DetectorGuardRail(ExactMatchDetector({"Emma": "PERSON"}))
        verdict = await guard.check("Hello <<PERSON:1>>")
        assert verdict.flagged is False


class TestPlaceholders:
    @pytest.mark.parametrize(
        ("text", "tagged"), PLACEHOLDER_ONLY.values(), ids=PLACEHOLDER_ONLY.keys()
    )
    async def test_a_detection_holding_only_placeholders_is_ignored(
        self, text: str, tagged: str
    ) -> None:
        """A detection with fewer than two letters or digits beside its tokens passes."""
        guard = DetectorGuardRail(_SpanDetector(tagged))
        verdict = await guard.check(text)
        assert verdict.flagged is False
        assert verdict.detections == ()

    @pytest.mark.parametrize(("text", "tagged"), RESIDUAL.values(), ids=RESIDUAL.keys())
    async def test_a_value_beside_placeholders_is_flagged(
        self, text: str, tagged: str
    ) -> None:
        """A detection keeping a value beside the placeholders still flags."""
        guard = DetectorGuardRail(_SpanDetector(tagged))
        verdict = await guard.check(text)
        assert verdict.flagged is True
        assert [detection.text for detection in verdict.detections] == [tagged]

    async def test_the_verdict_keeps_only_the_residual_detections(self) -> None:
        """Placeholder detections are dropped from the verdict, the leak stays."""
        guard = DetectorGuardRail(_SpanDetector("<<PERSON:1>>", "Emma"))
        verdict = await guard.check("<<PERSON:1>> and Emma")
        assert [detection.text for detection in verdict.detections] == ["Emma"]

    async def test_the_filter_can_be_turned_off(self) -> None:
        """With ignore_placeholders off, a detection on a placeholder flags."""
        guard = DetectorGuardRail(
            _SpanDetector("<<PERSON:1>>"),
            ignore_placeholders=False,
        )
        verdict = await guard.check("Hello <<PERSON:1>>.")
        assert verdict.flagged is True

    async def test_a_recognizer_sets_the_grammar(self) -> None:
        """A guard given a recognizer finds placeholders with its delimiters."""
        guard = DetectorGuardRail(
            _SpanDetector("[[PERSON:1]]"),
            recognizer=_custom_factory(),
        )
        verdict = await guard.check("Hello [[PERSON:1]].")
        assert verdict.flagged is False

    async def test_standalone_falls_back_to_the_default_grammar(self) -> None:
        """Alone, a guard does not know custom delimiters and flags their tokens."""
        guard = DetectorGuardRail(_SpanDetector("[[PERSON:1]]"))
        verdict = await guard.check("Hello [[PERSON:1]].")
        assert verdict.flagged is True


class TestPipelineGrammar:
    def _pipeline(
        self, guard: DetectorGuardRail, factory: LabelCounterPlaceholderFactory
    ) -> AnonymizationPipeline:
        """Build a pipeline masking Emma with the factory, re-checked by the guard."""
        anonymizer = Anonymizer(factory)
        return AnonymizationPipeline(
            ExactMatchDetector({"Emma": "PERSON"}),
            anonymizer=anonymizer,
            guard=guard,
        )

    async def test_a_guard_takes_the_pipeline_grammar(self) -> None:
        """In a pipeline with custom delimiters, the guard ignores their tokens."""
        guard = DetectorGuardRail(_SpanDetector("[[PERSON:1]]"))
        pipeline = self._pipeline(guard, _custom_factory())
        result = await pipeline.anonymize("Hello Emma.")
        assert result.text == "Hello [[PERSON:1]]."

    async def test_a_leak_still_raises_with_the_pipeline_grammar(self) -> None:
        """The pipeline grammar sets placeholders aside, not a value beside them."""
        guard = DetectorGuardRail(_SpanDetector("[[PERSON:1]] Doe"))
        pipeline = self._pipeline(guard, _custom_factory())
        with pytest.raises(PIIRemainingError):
            await pipeline.anonymize("Hello Emma Doe.")

    def test_the_caller_guard_is_left_unchanged(self) -> None:
        """The pipeline binds its grammar to a copy, not to the caller's guard."""
        guard = DetectorGuardRail(_SpanDetector("[[PERSON:1]]"))
        factory = _custom_factory()
        pipeline = self._pipeline(guard, factory)
        assert isinstance(pipeline.guard, DetectorGuardRail)
        assert pipeline.guard.recognizer is factory
        assert guard.recognizer is None

    def test_an_explicit_recognizer_is_kept(self) -> None:
        """A guard built with its own recognizer keeps it inside a pipeline."""
        own = LabelCounterPlaceholderFactory()
        guard = DetectorGuardRail(_SpanDetector("Emma"), recognizer=own)
        pipeline = self._pipeline(guard, _custom_factory())
        assert pipeline.guard is guard

    def test_a_pipeline_without_grammar_keeps_the_default(self) -> None:
        """A mask factory has no grammar, so the guard keeps the default one."""
        guard = DetectorGuardRail(_SpanDetector("Emma"))
        pipeline = AnonymizationPipeline(
            ExactMatchDetector({"Emma": "PERSON"}),
            anonymizer=Anonymizer(MaskPlaceholderFactory()),
            guard=guard,
        )
        assert pipeline.guard is guard
