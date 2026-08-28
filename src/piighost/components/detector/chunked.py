"""Chunked detector: run any detector over a long text via overlapping chunks."""

from dataclasses import replace

from piighost.components.detector.base import AnyDetector
from piighost.models import Detection
from piighost.text import AnySplitter, RecursiveCharacterTextSplitter


class ChunkedDetector:
    """Run a wrapped detector over each chunk of a long text.

    A decorator that is itself an AnyDetector. It splits the text into
    overlapping chunks, runs the wrapped detector on each, and remaps every
    detection back to the original text with Span.shift. The strictly identical
    detections the overlap produces are deduplicated; label conflicts and
    differing confidences flow through to the span-conflict stage.
    """

    def __init__(
        self,
        detector: AnyDetector,
        splitter: AnySplitter | None = None,
    ) -> None:
        """Wrap detector, chunking with splitter or a default one.

        Args:
            detector: The detector run on each chunk.
            splitter: The splitter, or None to use a default
                RecursiveCharacterTextSplitter.
        """
        self._detector = detector
        self._splitter = splitter or RecursiveCharacterTextSplitter()

    async def detect(self, text: str) -> list[Detection]:
        """Detect across chunks, remap offsets, and drop exact duplicates."""
        detections: list[Detection] = []
        for chunk in self._splitter.split(text):
            for detection in await self._detector.detect(chunk.text):
                span = detection.span.shift(chunk.start)
                remapped = replace(detection, span=span)
                detections.append(remapped)
        # dict.fromkeys drops the strictly identical detections the overlap
        # produces, order preserved. Label conflicts and differing confidences
        # are kept for the span-conflict stage.
        return list(dict.fromkeys(detections))
