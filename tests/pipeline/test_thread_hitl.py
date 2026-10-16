"""Tests for the ThreadAnonymizationPipeline HITL correction method."""

import pytest

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import AnyDetector, ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import (
    LabelCounterPlaceholderFactory,
    PreservesLabeledIdentityOpaque,
)
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.models import Detection, Span
from piighost.pipeline import ThreadAnonymizationPipeline


def _pipeline(
    detector: AnyDetector | None = None,
) -> ThreadAnonymizationPipeline[PreservesLabeledIdentityOpaque]:
    """Build a thread pipeline over a counter factory and in-memory backend."""
    return ThreadAnonymizationPipeline(
        detector or ExactMatchDetector({"Paris": "LOCATION"}),
        ExactEntityLinker(),
        Anonymizer(LabelCounterPlaceholderFactory()),
        InMemoryConversationMemory(),
    )


def _acme() -> list[Detection]:
    """A one-detection corrected set naming Acme at the start of the text."""
    return [Detection(span=Span(0, 4), text="Acme", label="ORG", confidence=1.0)]


def _human(text: str, value: str, label: str, confidence: float) -> Detection:
    """Build the human's detection of the first occurrence of value in text."""
    start = text.index(value)
    span = Span(start, start + len(value))
    return Detection(
        span=span,
        text=value,
        label=label,
        confidence=confidence,
    )


OVERLAPPING_CORRECTIONS: dict[str, tuple[str, dict[str, str], Detection, str]] = {
    "human_covers_the_automatic_span": (
        "Il y a nora.bzh dedans",
        {"nora": "PERSON"},
        _human("Il y a nora.bzh dedans", "nora.bzh", "USERNAME", 1.0),
        "Il y a <<USERNAME:1>> dedans",
    ),
    "spans_cross_so_the_union_is_hidden": (
        "Loni M. Wirth arrive",
        {"Loni M.": "PERSON"},
        _human("Loni M. Wirth arrive", "M. Wirth", "PERSON", 1.0),
        "<<PERSON:1>> arrive",
    ),
    "human_inside_an_equally_sure_automatic_span": (
        "Écris à nora.bzh@mail.fr",
        {"nora.bzh@mail.fr": "EMAIL_ADDRESS"},
        _human("Écris à nora.bzh@mail.fr", "nora.bzh", "USERNAME", 1.0),
        "Écris à <<USERNAME:1>>",
    ),
    "human_below_the_automatic_confidence": (
        "Il y a nora.bzh dedans",
        {"nora": "PERSON"},
        _human("Il y a nora.bzh dedans", "nora.bzh", "USERNAME", 0.5),
        "Il y a <<USERNAME:1>> dedans",
    ),
}
"""Corrections whose human detection overlaps an automatic one, by case name.

Each case holds the text, the automatic detector's values, the human's added
detection, and the expected render. The automatic detector scores 1.0, so the
human always faces a detection at least as sure as itself.
"""


class TestAnonymizeCorrected:
    async def test_adds_a_missed_value(self) -> None:
        """A corrected set adds a value the detector never found."""
        pipeline = _pipeline(ExactMatchDetector({}))
        result = await pipeline.anonymize_corrected("Acme rocks", "t1", _acme())
        assert result.text == "<<ORG:1>> rocks"

    async def test_drops_a_false_positive(self) -> None:
        """An empty corrected set leaves a mis-detected value in clear."""
        pipeline = _pipeline()
        first = await pipeline.anonymize("Visit Paris", "t1")
        assert first.text == "Visit <<LOCATION:1>>"
        corrected = await pipeline.anonymize_corrected("Visit Paris", "t1", [])
        assert corrected.text == "Visit Paris"

    async def test_added_value_is_deanonymizable_thread_wide(self) -> None:
        """A corrected addition enters the thread token map and is reversible."""
        pipeline = _pipeline(ExactMatchDetector({}))
        await pipeline.anonymize_corrected("Acme rocks", "t1", _acme())
        restored = await pipeline.deanonymize("<<ORG:1>>", "t1")
        assert restored == "Acme"

    async def test_correction_is_local_to_the_message(self) -> None:
        """Dropping a value from one message does not clear it in another."""
        pipeline = _pipeline()
        await pipeline.anonymize("Visit Paris", "t1")
        await pipeline.anonymize_corrected("Visit Paris", "t1", [])
        later = await pipeline.anonymize("Go to Paris", "t1")
        assert later.text == "Go to <<LOCATION:1>>"

    async def test_re_correcting_replaces_cleanly(self) -> None:
        """A second corrected set replaces the first rather than merging."""
        pipeline = _pipeline(ExactMatchDetector({}))
        await pipeline.anonymize_corrected("Acme rocks", "t1", _acme())
        replaced = await pipeline.anonymize_corrected("Acme rocks", "t1", [])
        assert replaced.text == "Acme rocks"


class TestOverlappingCorrection:
    @pytest.mark.parametrize(
        ("text", "automatic", "human", "expected"),
        OVERLAPPING_CORRECTIONS.values(),
        ids=OVERLAPPING_CORRECTIONS.keys(),
    )
    async def test_the_union_is_hidden_and_named_by_the_human(
        self,
        text: str,
        automatic: dict[str, str],
        human: Detection,
        expected: str,
    ) -> None:
        """Overlapping detections merge into one span the human's label names."""
        pipeline = _pipeline(ExactMatchDetector(automatic))
        await pipeline.anonymize(text, "t1")
        cached = await pipeline.memory.get_detections("t1", text) or []
        result = await pipeline.anonymize_corrected(text, "t1", [*cached, human])
        assert result.text == expected

    async def test_without_a_cached_set_the_surest_names_the_union(self) -> None:
        """A message never anonymized has no automatic set, so all are the human's."""
        text = "Il y a nora.bzh dedans"
        sure = _human(text, "nora", "PERSON", 1.0)
        unsure = _human(text, "nora.bzh", "USERNAME", 0.9)
        pipeline = _pipeline(ExactMatchDetector({}))
        result = await pipeline.anonymize_corrected(text, "t1", [sure, unsure])
        assert result.text == "Il y a <<PERSON:1>> dedans"
