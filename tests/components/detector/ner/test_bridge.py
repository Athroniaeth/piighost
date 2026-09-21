"""Tests for the BridgeDetector, which awaits a runner holding the model.

The runner is a plain coroutine returning canned span payloads, so the mapping,
the checks and the label filtering are exercised without any model or any
JavaScript runtime.
"""

from collections.abc import Sequence
from typing import Any

import pytest

from piighost.components.detector import AnyDetector
from piighost.components.detector.ner import BridgeDetector
from piighost.exceptions import BridgePayloadError, BridgeSpanRangeError

TEXT = "Emma Rossi works at Acme."
"""The text every case scans, with Emma Rossi at [0, 10) and Acme at [20, 24)."""


def _span(
    start: int = 0,
    end: int = 10,
    label: str = "person",
    score: float = 0.9,
) -> dict[str, Any]:
    """Build a span payload as a runner returns one, with sensible defaults."""
    return {"start": start, "end": end, "label": label, "score": score}


class _Runner:
    """A runner that answers with canned payloads and records how it was called.

    Attributes:
        calls: One entry per call, the text, the labels and the threshold.
    """

    def __init__(self, *payloads: dict[str, Any]) -> None:
        """Store the payloads to answer with and start an empty call log."""
        self._payloads = list(payloads)
        self.calls: list[tuple[str, list[str], float]] = []

    async def __call__(
        self, text: str, labels: list[str], threshold: float
    ) -> Sequence[dict[str, Any]]:
        """Record the call and return the canned payloads."""
        self.calls.append((text, labels, threshold))
        return list(self._payloads)


class _JsLikeList(list[Any]):
    """A sequence that converts on demand, as a Pyodide JsProxy does."""

    def to_py(self) -> list[Any]:
        """Return the plain Python list the proxy stands for."""
        return list(self)


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """BridgeDetector is an AnyDetector."""
        detector = BridgeDetector(_Runner(), {"PERSON": "person"})
        assert isinstance(detector, AnyDetector)


class TestDetect:
    async def test_maps_a_span_onto_a_detection(self) -> None:
        """A span payload becomes a detection carrying its offsets and label."""
        detector = BridgeDetector(_Runner(_span()), {"PERSON": "person"})

        detections = await detector.detect(TEXT)

        assert len(detections) == 1
        detection = detections[0]
        assert detection.span.start == 0
        assert detection.span.end == 10
        assert detection.label == "PERSON"
        assert detection.confidence == pytest.approx(0.9)

    async def test_text_is_read_from_the_source(self) -> None:
        """The detection's text is sliced from the source, not from the runner."""
        payload = _span()
        payload["text"] = "a value the runner mangled"
        detector = BridgeDetector(_Runner(payload), {"PERSON": "person"})

        detections = await detector.detect(TEXT)

        assert detections[0].text == "Emma Rossi"

    async def test_runner_is_called_with_the_internal_labels(self) -> None:
        """The runner is queried with the labels the model knows, and the threshold."""
        runner = _Runner()
        detector = BridgeDetector(runner, {"PERSON": "person"}, threshold=0.3)

        await detector.detect(TEXT)

        assert runner.calls == [(TEXT, ["person"], 0.3)]

    async def test_unmapped_label_is_dropped(self) -> None:
        """A span whose label is not in the map yields no detection."""
        payload = _span(label="vehicle")
        detector = BridgeDetector(_Runner(payload), {"PERSON": "person"})

        assert await detector.detect(TEXT) == []

    async def test_proxy_result_is_converted(self) -> None:
        """A result carrying to_py, as a JsProxy does, is converted first."""
        proxy = _JsLikeList([_span()])

        class _ProxyRunner:
            """A runner that answers with a proxy rather than a plain list."""

            async def __call__(
                self, text: str, labels: list[str], threshold: float
            ) -> Any:
                """Return the proxy, which the detector must convert."""
                return proxy

        detector = BridgeDetector(_ProxyRunner(), {"PERSON": "person"})

        detections = await detector.detect(TEXT)

        assert len(detections) == 1

    @pytest.mark.parametrize("score", [-0.4, 1.7])
    async def test_out_of_range_score_is_clamped(self, score: float) -> None:
        """A score outside [0, 1] is clamped rather than rejected as a detection."""
        detector = BridgeDetector(_Runner(_span(score=score)), {"PERSON": "person"})

        detections = await detector.detect(TEXT)

        assert 0.0 <= detections[0].confidence <= 1.0


class TestMalformedPayload:
    @pytest.mark.parametrize("missing", ["start", "end", "label", "score"])
    async def test_missing_field_is_refused(self, missing: str) -> None:
        """A span missing a required field raises rather than build a guess."""
        payload = _span()
        del payload[missing]
        detector = BridgeDetector(_Runner(payload), {"PERSON": "person"})

        with pytest.raises(BridgePayloadError):
            await detector.detect(TEXT)

    async def test_non_numeric_offset_is_refused(self) -> None:
        """An offset that is not a number raises rather than build a guess."""
        payload = _span()
        payload["start"] = "zero"
        detector = BridgeDetector(_Runner(payload), {"PERSON": "person"})

        with pytest.raises(BridgePayloadError):
            await detector.detect(TEXT)

    @pytest.mark.parametrize(
        ("start", "end"),
        [(-1, 10), (0, len(TEXT) + 1), (10, 10), (10, 4)],
    )
    async def test_span_outside_the_text_is_refused(self, start: int, end: int) -> None:
        """A span that overruns, inverts or is empty raises rather than be trimmed."""
        detector = BridgeDetector(
            _Runner(_span(start=start, end=end)), {"PERSON": "person"}
        )

        with pytest.raises(BridgeSpanRangeError):
            await detector.detect(TEXT)
