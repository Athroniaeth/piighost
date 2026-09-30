"""Tests for the BridgeDetector, which awaits a runner holding the model.

The runner is a plain coroutine returning canned span payloads, so the mapping,
the checks and the label filtering are exercised without any model or any
JavaScript runtime.
"""

from collections.abc import Sequence
from typing import Any

import pytest

from piighost.components.detector import AnyDetector
from piighost.components.detector.ner import BridgeDetector, OffsetUnit
from piighost.exceptions import BridgePayloadError, BridgeSpanRangeError

TEXT = "Emma Rossi works at Acme."
"""The text every case scans, with Emma Rossi at [0, 10) and Acme at [20, 24)."""

EMOJI_TEXT = "\U0001f642 Emma"
"""An emoji, then Emma at [2, 6) in code points and [3, 7) in UTF-16 units."""


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


def _detector(
    runner: Any, unit: OffsetUnit = OffsetUnit.CODE_POINT, threshold: float = 0.5
) -> BridgeDetector:
    """Build a BridgeDetector mapping PERSON onto the runner's person label."""
    return BridgeDetector(
        runner, {"PERSON": "person"}, offset_unit=unit, threshold=threshold
    )


class _JsProxy:
    """A result that is only readable once converted, as a Pyodide JsProxy is."""

    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        """Hold the payloads the conversion hands back."""
        self._payloads = payloads

    def to_py(self) -> list[dict[str, Any]]:
        """Return the plain Python list the proxy stands for."""
        return self._payloads


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """BridgeDetector is an AnyDetector."""
        assert isinstance(_detector(_Runner()), AnyDetector)


class TestDetect:
    async def test_maps_a_span_onto_a_detection(self) -> None:
        """A span payload becomes a detection carrying its offsets and label."""
        detections = await _detector(_Runner(_span())).detect(TEXT)

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
        detections = await _detector(_Runner(payload)).detect(TEXT)

        assert detections[0].text == "Emma Rossi"

    async def test_runner_is_called_with_the_internal_labels(self) -> None:
        """The runner is queried with the labels the model knows, and the threshold."""
        runner = _Runner()
        await _detector(runner, threshold=0.3).detect(TEXT)

        assert runner.calls == [(TEXT, ["person"], 0.3)]

    async def test_unmapped_label_is_dropped(self) -> None:
        """A span whose label is not in the map yields no detection."""
        payload = _span(label="vehicle")
        assert await _detector(_Runner(payload)).detect(TEXT) == []

    async def test_span_below_the_threshold_is_dropped(self) -> None:
        """A runner that ignores the threshold still lets nothing weaker through."""
        runner = _Runner(_span(score=0.9), _span(start=20, end=24, score=0.1))

        detections = await _detector(runner).detect(TEXT)

        assert [d.text for d in detections] == ["Emma Rossi"]

    @pytest.mark.parametrize(
        ("unit", "start", "end"),
        [(OffsetUnit.CODE_POINT, 2, 6), (OffsetUnit.UTF16, 3, 7)],
    )
    async def test_offsets_are_read_in_the_runner_unit(
        self, unit: OffsetUnit, start: int, end: int
    ) -> None:
        """A UTF-16 offset after an emoji lands on the same characters."""
        runner = _Runner(_span(start=start, end=end))

        detections = await _detector(runner, unit).detect(EMOJI_TEXT)

        assert detections[0].text == "Emma"

    async def test_proxy_result_is_converted(self) -> None:
        """A result carrying to_py, as a JsProxy does, is converted first."""
        proxy = _JsProxy([_span()])

        class _ProxyRunner:
            """A runner that answers with a proxy rather than a plain list."""

            async def __call__(
                self, text: str, labels: list[str], threshold: float
            ) -> Any:
                """Return the proxy, which the detector must convert."""
                return proxy

        detections = await _detector(_ProxyRunner()).detect(TEXT)

        assert [d.text for d in detections] == ["Emma Rossi"]

    @pytest.mark.parametrize("score", [-0.4, 1.7])
    async def test_out_of_range_score_is_clamped(self, score: float) -> None:
        """A score outside [0, 1] is clamped rather than rejected as a detection."""
        runner = _Runner(_span(score=score))

        detections = await _detector(runner, threshold=0.0).detect(TEXT)

        assert 0.0 <= detections[0].confidence <= 1.0


class TestMalformedPayload:
    @pytest.mark.parametrize("missing", ["start", "end", "label", "score"])
    async def test_missing_field_is_refused(self, missing: str) -> None:
        """A span missing a required field raises rather than build a guess."""
        payload = _span()
        del payload[missing]

        with pytest.raises(BridgePayloadError):
            await _detector(_Runner(payload)).detect(TEXT)

    @pytest.mark.parametrize("offset", ["zero", 8.9, 8.0, True])
    async def test_offset_that_is_not_an_integer_is_refused(
        self, offset: object
    ) -> None:
        """A string, a float or a bool raises rather than be truncated to a guess."""
        payload = _span()
        payload["start"] = offset

        with pytest.raises(BridgePayloadError):
            await _detector(_Runner(payload)).detect(TEXT)

    @pytest.mark.parametrize(
        ("start", "end"),
        [(-1, 10), (0, len(TEXT) + 1), (10, 10), (10, 4)],
    )
    async def test_span_outside_the_text_is_refused(self, start: int, end: int) -> None:
        """A span that overruns, inverts or is empty raises rather than be trimmed."""
        with pytest.raises(BridgeSpanRangeError):
            await _detector(_Runner(_span(start=start, end=end))).detect(TEXT)

    async def test_utf16_offset_inside_an_emoji_is_refused(self) -> None:
        """An offset between the two halves of an emoji names no character."""
        runner = _Runner(_span(start=1, end=7))

        with pytest.raises(BridgeSpanRangeError):
            await _detector(runner, OffsetUnit.UTF16).detect(EMOJI_TEXT)
