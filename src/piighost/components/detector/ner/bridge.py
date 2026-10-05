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

import operator
from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from piighost.components.detector.ner.base import BaseNERDetector
from piighost.exceptions import BridgePayloadError, BridgeSpanRangeError
from piighost.models import Detection, Span


class OffsetUnit(Enum):
    """What a runner counts when it reports an offset.

    A Span counts code points, as a Python str does. JavaScript counts UTF-16
    code units, where a character outside the Basic Multilingual Plane, an emoji
    or a rare CJK ideograph, takes two. The two agree on a text without such a
    character and drift apart by one after each, so a JavaScript offset read as
    a code point lands one character late, and the first letter of the value
    stays in clear.
    """

    CODE_POINT = "code_point"
    """Python's unit, what a runner written in Python reports."""

    UTF16 = "utf16"
    """JavaScript's unit, what a runner in a browser or in Node reports."""


@runtime_checkable
class AnySpanRunner(Protocol):
    """A callable that scores spans of a text against a list of labels.

    The return value is a sequence of mappings, one per span, carrying start,
    end, label and score. A start and end are offsets into the text passed in,
    half-open, as Span is, counted in the unit the detector is told. Any text
    the runner returns is ignored and re-read from the source, so a runner that
    mangles the matched substring cannot desynchronise the replacement.
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
    offset_unit is required too. A wrong guess shifts every span that follows
    an emoji, and nothing in the payload tells the two units apart.

    Attributes:
        runner: The callable awaited for each text, holding the model.
        offset_unit: What the runner counts in its offsets.
    """

    def __init__(
        self,
        runner: AnySpanRunner,
        labels: list[str] | dict[str, str],
        *,
        offset_unit: OffsetUnit,
        threshold: float = 0.5,
        max_chars: int | None = None,
        auto_chunk: bool = True,
    ) -> None:
        """Store the runner and its offset unit, then set up the base.

        threshold is passed to the runner, so it can filter before crossing the
        boundary, and applied again by the base, so a runner that ignores it
        lets nothing weaker through.
        """
        super().__init__(
            labels, threshold=threshold, max_chars=max_chars, auto_chunk=auto_chunk
        )
        self.runner = runner
        self.offset_unit = offset_unit

    async def _raw_detect(self, text: str) -> list[Detection]:
        """Await the runner and build one detection per span it returned.

        Raises:
            BridgePayloadError: If a span is missing a field or carries offsets
                that are not integers.
            BridgeSpanRangeError: If a span falls outside the text, or inside a
                character.
        """
        spans = await self.runner(text, self.internal_labels, self.threshold)
        # A Pyodide JsProxy converts to Python on demand; a plain sequence does
        # not need it. Duck-typing it keeps pyodide out of the core's imports.
        converter = getattr(spans, "to_py", None)
        if converter is not None:
            spans = converter()

        positions = self._positions(text)
        return [self._build(payload, text, positions) for payload in spans]

    def _positions(self, text: str) -> dict[int, int] | None:
        """Map each UTF-16 offset between two characters to its code point offset.

        An offset that splits a character, or lies past the end, is not a key.
        None means the runner's offsets are already code points, because it
        counts them or because the text holds no character that takes two units.
        """
        if self.offset_unit is OffsetUnit.CODE_POINT or all(
            ord(char) <= 0xFFFF for char in text
        ):
            return None
        positions: dict[int, int] = {}
        unit = 0
        for index, char in enumerate(text):
            positions[unit] = index
            unit += 2 if ord(char) > 0xFFFF else 1
        positions[unit] = len(text)
        return positions

    @staticmethod
    def _build(
        payload: Mapping[str, Any], text: str, positions: dict[int, int] | None
    ) -> Detection:
        """Turn one span payload into a detection, checking it against the text.

        Raises:
            BridgePayloadError: If the payload is missing a field or malformed.
            BridgeSpanRangeError: If the span falls outside the text, or inside
                a character.
        """
        try:
            start = _offset(payload["start"])
            end = _offset(payload["end"])
            label = str(payload["label"])
            score = float(payload["score"])
        except (KeyError, TypeError, ValueError) as exc:
            raise BridgePayloadError(
                f"The runner returned a span this detector cannot read: {payload!r}. "
                f"A span needs start, end, label and score, with integer offsets."
            ) from exc

        first = _locate(start, positions, len(text))
        last = _locate(end, positions, len(text))
        if first is None or last is None or first >= last:
            raise BridgeSpanRangeError(
                f"The runner returned the span [{start}, {end}), which is empty, "
                f"inverted, or not between two characters of the {len(text)} it "
                f"was given."
            )

        span = Span(first, last)
        clamped = min(1.0, max(0.0, score))
        return Detection(
            span=span,
            text=span.extract(text),
            label=label,
            confidence=clamped,
        )


def _locate(offset: int, positions: dict[int, int] | None, length: int) -> int | None:
    """Return the code point offset a runner's offset stands for, or None.

    None means the offset lies outside the text, or inside a character.
    """
    if positions is not None:
        return positions.get(offset)
    return offset if 0 <= offset <= length else None


def _offset(value: Any) -> int:
    """Return an offset as an int, refusing a float, a bool or a string.

    A float offset is a runner bug, and truncating it would move the span.
    operator.index accepts any integer type, numpy's included, and nothing else.

    Raises:
        TypeError: If the value is not an integer.
    """
    if isinstance(value, bool):
        raise TypeError(f"An offset cannot be a bool: {value!r}.")
    return operator.index(value)
