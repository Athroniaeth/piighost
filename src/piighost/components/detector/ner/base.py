"""Base for NER detectors: a shared label-mapping pass over a model hook.

BaseNERDetector is a Template Method. Its detect runs the abstract _raw_detect,
which each adapter implements around its own model, then applies one shared
label-mapping and filtering pass. Adapters therefore hold only backend-specific
extraction, not the mapping loop.
"""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from piighost.exceptions import LabelMappingError
from piighost.models import Detection


class BaseNERDetector(ABC):
    """Abstract base for detectors backed by a NER model.

    It normalizes the labels argument into an external-to-internal map, builds
    the internal-to-external reverse lookup, and provides a concrete detect that
    maps and filters the detections a subclass produces.

    A label map distinguishes the label a model uses internally from the label
    emitted in Detection.label. An empty map means no mapping, so every
    detection is kept with the label the model gave it. A non-empty map keeps
    only detections whose native label is mapped, relabeling each to its
    external label and dropping the rest.
    """

    def __init__(
        self,
        labels: list[str] | dict[str, str] | None,
        max_concurrency: int | None = None,
    ) -> None:
        """Normalize labels, build the reverse lookup, and set concurrency."""
        self._label_map = self._normalize(labels)
        self._reverse_map = self._build_reverse(self._label_map)
        self._infer_semaphore = (
            asyncio.Semaphore(max_concurrency) if max_concurrency else None
        )

    async def detect(self, text: str) -> list[Detection]:
        """Detect via the subclass hook, then map and filter the labels."""
        detections: list[Detection] = []
        for detection in await self._raw_detect(text):
            label = self._resolve_label(detection.label)
            if label is None:
                continue
            if label != detection.label:
                detection = replace(detection, label=label)
            detections.append(detection)
        return detections

    @abstractmethod
    async def _raw_detect(self, text: str) -> list[Detection]:
        """Return the model's detections with their native labels.

        Implementations run the model, build a Detection per entity with the
        native label, the span, and the confidence, and return them. All label
        mapping and filtering happens in detect, not here.
        """
        ...

    def _resolve_label(self, native: str) -> str | None:
        """Return the external label for a native one, or None to drop it.

        With an empty map every native label is kept unchanged. With a non-empty
        map, a native label absent from it is dropped.
        """
        if not self._label_map:
            return native
        return self._map_label(native)

    @staticmethod
    def _normalize(labels: list[str] | dict[str, str] | None) -> dict[str, str]:
        """Turn the labels argument into an external-to-internal map."""
        if labels is None:
            return {}
        if isinstance(labels, list):
            return {label: label for label in labels}
        return dict(labels)

    @staticmethod
    def _build_reverse(label_map: dict[str, str]) -> dict[str, str]:
        """Build the internal-to-external reverse lookup.

        Raises LabelMappingError when two external labels map to one internal
        label, which would make the reverse lookup ambiguous.
        """
        reverse: dict[str, str] = {}
        for external, internal in label_map.items():
            if internal in reverse:
                raise LabelMappingError(
                    f"Label mapping conflict: internal label '{internal}' is "
                    f"used by both '{reverse[internal]}' and '{external}'."
                )
            reverse[internal] = external
        return reverse

    @property
    def internal_labels(self) -> list[str]:
        """The labels passed to or filtered on by the model (map values)."""
        return list(self._label_map.values())

    @property
    def external_labels(self) -> list[str]:
        """The labels emitted in Detection.label (map keys)."""
        return list(self._label_map.keys())

    def _map_label(self, internal: str) -> str | None:
        """Return the external label for an internal one, or None if unmapped."""
        return self._reverse_map.get(internal)

    async def _run_blocking(
        self, fn: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        """Run a blocking callable off the event loop, optionally bounded.

        Offloads fn via asyncio.to_thread so synchronous model inference does not
        block the loop. When max_concurrency was set, a semaphore caps how many
        inferences run at once.
        """
        if self._infer_semaphore is None:
            return await asyncio.to_thread(fn, *args, **kwargs)
        async with self._infer_semaphore:
            return await asyncio.to_thread(fn, *args, **kwargs)
