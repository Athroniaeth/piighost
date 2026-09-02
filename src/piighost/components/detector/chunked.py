"""Chunked detector: run any detector over a long text via overlapping chunks."""

import asyncio
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
        """Detect across chunks, remap offsets, and drop exact duplicates.

        The chunks are scanned concurrently, so an I/O-bound detector such as the
        LLM one overlaps its calls. A local-model detector still bounds its own
        concurrency through its max_concurrency, so this does not oversubscribe it.
        """
        chunks = self._splitter.split(text)
        results = await asyncio.gather(
            *(self._detector.detect(chunk.text) for chunk in chunks)
        )

        detections: list[Detection] = []
        for chunk, chunk_detections in zip(chunks, results, strict=True):
            for detection in chunk_detections:
                span = detection.span.shift(chunk.start)
                detections.append(replace(detection, span=span))
        # dict.fromkeys drops the strictly identical detections the overlap
        # produces, order preserved. Label conflicts and differing confidences
        # are kept for the span-conflict stage.
        return list(dict.fromkeys(detections))
