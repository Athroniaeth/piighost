"""The contract every detector keeps, whatever finds the value.

Each case builds one detector over a fake backend, or over a pattern for the
rule-based ones, and scans the same text. The backends answer as a careless
model would: the value's text mangled, and a second span scored below the
threshold. Every detector must still report the value alone, at its code point
span, with the text of the source and the external label. The adapters behind
an optional extra skip when it is absent.
"""

from collections.abc import Callable
from typing import Any

import pytest

from piighost.components.detector import (
    AnyDetector,
    ExactMatchDetector,
    RegexDetector,
)
from piighost.components.detector.ner import BridgeDetector, OffsetUnit
from piighost.models import Span

TEXT = "Thanks \U0001f642 Emma Rossi works at Acme."
"""The value sits after an emoji, which Python counts as one and JavaScript as two."""

VALUE = (Span(9, 19), "Emma Rossi", "PERSON")
"""What every detector reports: the code point span, its text, its label."""

LABELS = {"PERSON": "person"}
"""The external label and the native one every model answers with."""

THRESHOLD = 0.5
"""The threshold every scored detector is built with."""

MANGLED = "Emma"
"""The text a fake backend returns for the value, which no detector may keep."""

FOUND = [(9, 19, 0.9), (29, 33, 0.1)]
"""What a fake model finds, in code points: the value, and Acme below threshold."""


def _bridge(unit: OffsetUnit, shift: int) -> AnyDetector:
    """Build a BridgeDetector whose runner counts its offsets in unit."""

    async def runner(
        text: str, labels: list[str], threshold: float
    ) -> list[dict[str, Any]]:
        return [
            {"start": start + shift, "end": end + shift, "label": "person"}
            | {"score": score, "text": MANGLED}
            for start, end, score in FOUND
        ]

    return BridgeDetector(runner, LABELS, offset_unit=unit, threshold=THRESHOLD)


def _gliner2() -> AnyDetector:
    """Build a Gliner2Detector over a model that ignores the threshold."""
    pytest.importorskip("gliner2")
    from piighost.components.detector.ner import Gliner2Detector

    class _Model:
        def extract_entities(
            self, text: str, labels: list[str], **kwargs: object
        ) -> dict[str, object]:
            entities = [
                {"text": MANGLED, "start": start, "end": end, "confidence": score}
                for start, end, score in FOUND
            ]
            return {"entities": {"person": entities}}

    return Gliner2Detector(model=_Model(), labels=LABELS, threshold=THRESHOLD)


def _transformers() -> AnyDetector:
    """Build a TransformersDetector over a pipeline of canned entities."""
    pytest.importorskip("transformers")
    from piighost.components.detector.ner import TransformersDetector

    def pipeline(text: str) -> list[dict[str, object]]:
        return [
            {"entity_group": "person", "score": score, "start": start, "end": end}
            for start, end, score in FOUND
        ]

    return TransformersDetector(pipeline=pipeline, labels=LABELS, threshold=THRESHOLD)


def _presidio() -> AnyDetector:
    """Build a PresidioDetector over an analyzer that ignores the threshold."""
    pytest.importorskip("presidio_analyzer")
    from types import SimpleNamespace

    from piighost.components.detector.ner import PresidioDetector

    class _Analyzer:
        def analyze(self, text: str, **kwargs: object) -> list[SimpleNamespace]:
            return [
                SimpleNamespace(entity_type="person", start=start, end=end, score=score)
                for start, end, score in FOUND
            ]

    return PresidioDetector(analyzer=_Analyzer(), labels=LABELS, threshold=THRESHOLD)


def _spacy() -> AnyDetector:
    """Build a SpacyDetector over a model that finds the value only, unscored."""
    pytest.importorskip("spacy")
    from types import SimpleNamespace

    from piighost.components.detector.ner import SpacyDetector

    start, end, _ = FOUND[0]
    entity = SimpleNamespace(
        text=MANGLED, label_="person", start_char=start, end_char=end
    )
    return SpacyDetector(
        model=lambda text: SimpleNamespace(ents=[entity]), labels=LABELS
    )


def _llm() -> AnyDetector:
    """Build an LLMDetector over a chat model that names the value."""
    from types import SimpleNamespace

    from piighost.components.detector import LLMDetector

    entity = SimpleNamespace(text="Emma Rossi", label=SimpleNamespace(value="person"))
    extraction = SimpleNamespace(entities=[entity])

    class _Structured:
        async def ainvoke(self, messages: object, **kwargs: object) -> object:
            return extraction

    class _Model:
        def with_structured_output(
            self, schema: object, **kwargs: object
        ) -> _Structured:
            return _Structured()

    return LLMDetector(model=_Model(), labels=LABELS)  # type: ignore[arg-type]


DETECTORS: list[Any] = [
    pytest.param(lambda: RegexDetector({"PERSON": r"Emma Rossi"}), id="regex"),
    pytest.param(lambda: ExactMatchDetector({"Emma Rossi": "PERSON"}), id="exact"),
    pytest.param(lambda: _bridge(OffsetUnit.CODE_POINT, 0), id="bridge-code-points"),
    pytest.param(lambda: _bridge(OffsetUnit.UTF16, 1), id="bridge-utf16"),
    pytest.param(_gliner2, id="gliner2"),
    pytest.param(_transformers, id="transformers"),
    pytest.param(_presidio, id="presidio"),
    pytest.param(_spacy, id="spacy"),
    pytest.param(_llm, id="llm"),
]
"""One builder per detector, each scanning TEXT for the same value."""


@pytest.mark.parametrize("build", DETECTORS)
async def test_every_detector_reports_the_value_the_same_way(
    build: Callable[[], AnyDetector],
) -> None:
    """The span in code points, the source's text, the external label, nothing weak."""
    detections = await build().detect(TEXT)

    assert [(d.span, d.text, d.label) for d in detections] == [VALUE]
    assert all(0.0 <= d.confidence <= 1.0 for d in detections)
