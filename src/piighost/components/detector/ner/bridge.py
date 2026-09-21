"""Bridge detector: delegates inference to an injected async callable.

The model runs outside Python, and this adapter only maps what it returns onto
the domain model. It exists for the browser, where no NER stack is installable:
Pyodide has neither torch nor transformers nor onnxruntime, so the model runs in
the host's JavaScript runtime and Python awaits it through the Pyodide FFI. The
same shape serves any out-of-process runner, a subprocess or a sidecar.

There is no configuration model for this detector. Its runner is a callable,
which a TOML or JSON file cannot name without a registry of callables, and that
registry would make the core depend on what configures it. A caller that builds
this detector builds it in code.
"""

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

from piighost.components.detector.ner.base import BaseNERDetector
from piighost.exceptions import BridgePayloadError, BridgeSpanRangeError
from piighost.models import Detection, Span


@runtime_checkable
class AnySpanRunner(Protocol):
    """A callable that scores spans of a text against a list of labels.

    The return value is a sequence of mappings, one per span, carrying start,
    end, label and score. A start and end are character offsets into the text
    passed in, half-open, as Span is. Any text the runner returns is ignored and
    re-read from the source, so a runner that mangles the matched substring
    cannot desynchronise the replacement.
    """

    async def __call__(
        self, text: str, labels: list[str], threshold: float
    ) -> Sequence[Mapping[str, Any]]:
        """Return the spans found in text, at or above threshold."""
        ...


class BridgeDetector(BaseNERDetector):
    """Detect PII by awaiting a runner that holds the model.

    labels is required, because the runner is queried with the internal labels,
    and a span whose label is not mapped is dropped, as for any NER adapter.

    Attributes:
        runner: The callable awaited for each text, holding the model.
        threshold: The confidence at or above which a span is kept, passed to
            the runner so it can filter before crossing the boundary.
    """

    def __init__(
        self,
        runner: AnySpanRunner,
        labels: list[str] | dict[str, str],
        threshold: float = 0.5,
        max_chars: int | None = None,
        auto_chunk: bool = True,
    ) -> None:
        """Store the runner and the threshold, then set up the label mapping."""
        super().__init__(labels, max_chars=max_chars, auto_chunk=auto_chunk)
        self.runner = runner
        self.threshold = threshold

    async def _raw_detect(self, text: str) -> list[Detection]:
        """Await the runner and build one detection per span it returned.

        Raises:
            BridgePayloadError: If a span is missing a field or carries offsets
                that are not integers.
            BridgeSpanRangeError: If a span falls outside the text.
        """
        spans = await self.runner(text, self.internal_labels, self.threshold)
        # A Pyodide JsProxy converts to Python on demand; a plain sequence does
        # not need it. Duck-typing it keeps pyodide out of the core's imports.
        converter = getattr(spans, "to_py", None)
        if converter is not None:
            spans = converter()

        detections: list[Detection] = []
        for span_payload in spans:
            detection = self._build(span_payload, text)
            detections.append(detection)
        return detections

    @staticmethod
    def _build(payload: Mapping[str, Any], text: str) -> Detection:
        """Turn one span payload into a detection, checking it against the text.

        Raises:
            BridgePayloadError: If the payload is missing a field or malformed.
            BridgeSpanRangeError: If the span falls outside the text.
        """
        try:
            start = int(payload["start"])
            end = int(payload["end"])
            label = str(payload["label"])
            score = float(payload["score"])
        except (KeyError, TypeError, ValueError) as exc:
            raise BridgePayloadError(
                f"The runner returned a span this detector cannot read: {payload!r}. "
                f"A span needs start, end, label and score."
            ) from exc

        if not 0 <= start < end <= len(text):
            raise BridgeSpanRangeError(
                f"The runner returned the span [{start}, {end}), which falls "
                f"outside the {len(text)} characters it was given."
            )

        span = Span(start, end)
        matched = span.extract(text)
        clamped = min(1.0, max(0.0, score))
        return Detection(
            span=span,
            text=matched,
            label=label,
            confidence=clamped,
        )
