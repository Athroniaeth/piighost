# NER Detectors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `BaseNERDetector` Template Method and three model-backed adapters (`Gliner2Detector`, `SpacyDetector`, `TransformersDetector`), each behind its optional extra, sharing one label-mapping pass.

**Architecture:** A new sub-package `components/detector/ner/`. `BaseNERDetector` (no optional import) holds a concrete `detect` that maps and filters the detections produced by the abstract `_raw_detect` hook; each adapter implements only backend-specific extraction and accepts a loaded model or a model-name `str` to load. The package exports `BaseNERDetector` eagerly and the three adapters via a lazy `__getattr__`.

**Tech Stack:** Python 3.11+, `asyncio`, `dataclasses.replace`, pytest (`asyncio_mode = "auto"`). Optional backends gliner2 / spacy / transformers, none installed in the dev venv.

---

## Conventions for every task

- Run tests with `uv run --no-sync`. Before each pytest run clear bytecode: `find src tests -name __pycache__ -type d -exec rm -rf {} +`.
- `asyncio_mode = "auto"`: `async def test_...` needs NO decorator.
- Python 3.11+ native typing, NO `from __future__ import annotations`. Docstrings plain prose plus bullet lists only, no markdown/RST (`::`, `:class:`). English only. Conventional Commits.
- `Detection(span=Span(start, end), text=..., label=..., confidence=...)`, frozen dataclass. `Span(start, end)` is half-open and rejects `end <= start`.
- The dev venv has NO gliner2 / spacy / transformers / torch. Therefore:
  - The three adapter modules import a package pyrefly cannot resolve. Suppress that one error per import line with a trailing `# pyrefly: ignore[missing-import]` comment (verified to suppress cleanly). The optional import also needs `# noqa: E402` because it follows the `find_spec` guard.
  - Adapter conformance and integration tests use `pytest.importorskip("<pkg>")` and SKIP locally. Do not expect them to pass in the dev venv; verify they are collected and skipped, not errored.
  - `pyrefly check src/piighost` must still report 0 errors (suppressions make the adapter imports clean).

## File structure

- Modify `src/piighost/exceptions.py` — add `DetectorError`, `LabelMappingError` (Task 1).
- Create `src/piighost/components/detector/ner/base.py` — `BaseNERDetector` (Task 2).
- Create `src/piighost/components/detector/ner/__init__.py` — eager `BaseNERDetector`, lazy adapters (Task 2).
- Create `src/piighost/components/detector/ner/gliner2.py` (Task 3).
- Create `src/piighost/components/detector/ner/spacy.py` (Task 4).
- Create `src/piighost/components/detector/ner/transformers.py` (Task 5).
- Modify `tests/regression/test_imports.py` — add `BaseNERDetector` (Task 6).
- Tests: `tests/components/detector/ner/test_base.py`, `test_gliner2.py`, `test_spacy.py`, `test_transformers.py`.

---

### Task 1: Detector exception family

**Files:**
- Modify: `src/piighost/exceptions.py`
- Test: `tests/test_exceptions.py` (create if absent) or an inline test module `tests/components/detector/ner/test_errors.py`

- [ ] **Step 1: Write the failing test**

Create `tests/components/detector/ner/test_errors.py`:

```python
"""Tests for the detector exception family."""

from piighost.exceptions import DetectorError, LabelMappingError, PIIGhostError


def test_detector_error_is_a_piighost_error() -> None:
    """DetectorError sits under the shared PIIGhostError root."""
    assert issubclass(DetectorError, PIIGhostError)


def test_label_mapping_error_is_a_detector_error() -> None:
    """LabelMappingError is a DetectorError, catchable as either."""
    assert issubclass(LabelMappingError, DetectorError)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/components/detector/ner/test_errors.py -q`
Expected: FAIL with `ImportError: cannot import name 'DetectorError'`.

- [ ] **Step 3: Add the exceptions**

In `src/piighost/exceptions.py`, after the `MixedLabelError` class (the end of the Entity error group) add:

```python
class DetectorError(PIIGhostError):
    """Base class for errors raised while constructing a detector.

    Catch this to handle any invalid-detector case at once, or catch one of its
    subclasses to react to a specific violation.
    """


class LabelMappingError(DetectorError):
    """Raised when a detector's label map has an ambiguous reverse lookup.

    Two external labels that map to the same internal label would make the
    internal-to-external lookup ambiguous, so the detector fails closed rather
    than pick one silently.
    """
```

- [ ] **Step 4: Run it to verify it passes**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/components/detector/ner/test_errors.py -q`
Expected: PASS, 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/piighost/exceptions.py tests/components/detector/ner/test_errors.py
git commit -m "feat(detector): add the detector exception family"
```

---

### Task 2: BaseNERDetector Template Method

**Files:**
- Create: `src/piighost/components/detector/ner/base.py`
- Create: `src/piighost/components/detector/ner/__init__.py`
- Test: `tests/components/detector/ner/test_base.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/components/detector/ner/test_base.py`:

```python
"""Tests for the BaseNERDetector Template Method.

A fake subclass supplies canned raw detections so the shared label-mapping and
filtering logic is exercised without loading any model.
"""

import pytest

from piighost.components.detector import AnyDetector
from piighost.components.detector.ner import BaseNERDetector
from piighost.exceptions import LabelMappingError
from piighost.models import Detection, Span


class _FakeNERDetector(BaseNERDetector):
    """A BaseNERDetector whose raw detections are injected, no model."""

    def __init__(self, raw, labels=None, max_concurrency=None):
        super().__init__(labels, max_concurrency=max_concurrency)
        self._raw = raw

    async def _raw_detect(self, text: str) -> list[Detection]:
        return self._raw


def _det(label: str, confidence: float = 0.9) -> Detection:
    """Build a Detection at a fixed span for a native label."""
    return Detection(span=Span(0, 4), text="Emma", label=label, confidence=confidence)


class TestConformance:
    def test_satisfies_the_detector_port(self) -> None:
        """A BaseNERDetector subclass is an AnyDetector."""
        assert isinstance(_FakeNERDetector([]), AnyDetector)


class TestLabelMapping:
    async def test_identity_list_keeps_mapped_and_drops_the_rest(self) -> None:
        """A list maps labels to themselves and drops any not listed."""
        detector = _FakeNERDetector([_det("PERSON"), _det("ORG")], labels=["PERSON"])
        detections = await detector.detect("Emma")
        assert [d.label for d in detections] == ["PERSON"]

    async def test_dict_relabels_native_to_external(self) -> None:
        """A dict rewrites the native label to its external label."""
        detector = _FakeNERDetector([_det("PER")], labels={"PERSON": "PER"})
        detections = await detector.detect("Emma")
        assert len(detections) == 1
        assert detections[0].label == "PERSON"
        assert detections[0].span == Span(0, 4)
        assert detections[0].confidence == 0.9

    async def test_dict_drops_unmapped_native_labels(self) -> None:
        """With a non-empty map, an unmapped native label is dropped."""
        detector = _FakeNERDetector([_det("LOC")], labels={"PERSON": "PER"})
        assert await detector.detect("Emma") == []

    async def test_empty_map_keeps_every_native_label(self) -> None:
        """With no map, every detection is kept with its native label."""
        detector = _FakeNERDetector([_det("PER"), _det("WHATEVER")])
        labels = [d.label for d in await detector.detect("Emma")]
        assert labels == ["PER", "WHATEVER"]

    def test_ambiguous_reverse_map_is_refused(self) -> None:
        """Two external labels for one internal label raise LabelMappingError."""
        with pytest.raises(LabelMappingError, match="conflict"):
            _FakeNERDetector([], labels={"PERSON": "X", "COMPANY": "X"})

    def test_internal_and_external_labels(self) -> None:
        """internal_labels are the map values, external_labels the keys."""
        detector = _FakeNERDetector([], labels={"PERSON": "per", "COMPANY": "org"})
        assert detector.internal_labels == ["per", "org"]
        assert detector.external_labels == ["PERSON", "COMPANY"]


class TestRunBlocking:
    async def test_runs_a_blocking_callable_off_the_loop(self) -> None:
        """_run_blocking returns the callable's result."""
        detector = _FakeNERDetector([])
        assert await detector._run_blocking(lambda value: value * 2, 21) == 42

    async def test_bounded_run_blocking_still_returns(self) -> None:
        """With max_concurrency set, the semaphore path still returns."""
        detector = _FakeNERDetector([], max_concurrency=1)
        assert await detector._run_blocking(lambda value: value + 1, 41) == 42
```

- [ ] **Step 2: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/components/detector/ner/test_base.py -q`
Expected: FAIL with `ModuleNotFoundError`/`ImportError` on `piighost.components.detector.ner`.

- [ ] **Step 3: Write the base and the package init**

Create `src/piighost/components/detector/ner/base.py`:

```python
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
```

Create `src/piighost/components/detector/ner/__init__.py`. It exports only
`BaseNERDetector` for now; each adapter task extends it with its own lazy branch,
so the tree stays green (pyrefly cannot resolve an adapter module before it
exists):

```python
"""NER detectors: model-backed adapters over a shared label-mapping base.

BaseNERDetector holds the shared logic and imports nothing optional. Concrete
model-backed adapters, each behind its own optional extra, are added here as
they land, exposed lazily so a missing extra fails only on access.
"""

from piighost.components.detector.ner.base import BaseNERDetector

__all__ = ["BaseNERDetector"]
```

- [ ] **Step 4: Run it to verify it passes**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/components/detector/ner/test_base.py -q`
Expected: PASS, 9 passed.

- [ ] **Step 5: Verify lint and types**

Run: `uv run --no-sync ruff format src/piighost/components/detector/ner tests/components/detector/ner && uv run --no-sync ruff check src/piighost/components/detector/ner && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean, pyrefly 0 errors.

- [ ] **Step 6: Commit**

```bash
git add src/piighost/components/detector/ner/base.py src/piighost/components/detector/ner/__init__.py tests/components/detector/ner/test_base.py
git commit -m "feat(detector): add the BaseNERDetector template method"
```

---

### Task 3: Gliner2Detector

**Files:**
- Create: `src/piighost/components/detector/ner/gliner2.py`
- Modify: `src/piighost/components/detector/ner/__init__.py`
- Test: `tests/components/detector/ner/test_gliner2.py`

- [ ] **Step 1: Write the tests**

Create `tests/components/detector/ner/test_gliner2.py`:

```python
"""Tests for the Gliner2Detector.

Conformance injects a fake model (no download); the integration test loads a
real GLiNER2 model and is marked integration. Both skip when gliner2 is absent.
"""

import pytest

from piighost.components.detector import AnyDetector


class _FakeGliner2:
    """A stand-in exposing the one method the adapter calls."""

    def extract_entities(self, text, **kwargs):
        return {"entities": {}}


class TestConformance:
    def test_satisfies_the_detector_port(self) -> None:
        """Gliner2Detector built on an injected model is an AnyDetector."""
        pytest.importorskip("gliner2")
        from piighost.components.detector.ner import Gliner2Detector

        detector = Gliner2Detector(model=_FakeGliner2(), labels=["PERSON"])
        assert isinstance(detector, AnyDetector)

    async def test_maps_native_labels_through_the_base(self) -> None:
        """A fake model's entities are relabeled by the base label map."""
        pytest.importorskip("gliner2")
        from piighost.components.detector.ner import Gliner2Detector

        class _Model:
            def extract_entities(self, text, **kwargs):
                return {
                    "entities": {
                        "person": [
                            {"text": "Emma", "start": 0, "end": 4, "confidence": 0.9}
                        ]
                    }
                }

        detector = Gliner2Detector(model=_Model(), labels={"PERSON": "person"})
        detections = await detector.detect("Emma is here")
        assert len(detections) == 1
        assert detections[0].label == "PERSON"
        assert detections[0].text == "Emma"
        assert detections[0].confidence == 0.9


@pytest.mark.integration
class TestIntegration:
    async def test_detects_a_person_with_a_real_model(self) -> None:
        """A real GLiNER2 model finds a person in a simple sentence."""
        pytest.importorskip("gliner2")
        from piighost.components.detector.ner import Gliner2Detector

        detector = Gliner2Detector(
            model="fastino/gliner2-multi-v1", labels=["PERSON"]
        )
        detections = await detector.detect("My name is Patrick.")
        assert any(d.label == "PERSON" for d in detections)
```

- [ ] **Step 2: Run it to verify current state**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/components/detector/ner/test_gliner2.py -q`
Expected: all tests SKIP (gliner2 absent) — `importorskip` skips them. This confirms the file collects cleanly.

- [ ] **Step 3: Write the adapter**

Create `src/piighost/components/detector/ner/gliner2.py`:

```python
"""GLiNER2 detector (optional: gliner2).

Wraps a GLiNER2 model so a caller injects a loaded instance or passes a model
name to load. This module needs the gliner2 package; it is guarded so importing
it without the dependency raises an ImportError pointing at the extra.
"""

import importlib.util

from piighost.components.detector.ner.base import BaseNERDetector
from piighost.models import Detection, Span

if importlib.util.find_spec("gliner2") is None:
    raise ImportError(
        "Gliner2Detector requires the gliner2 package. "
        "Install it with: pip install piighost[gliner2]"
    )

from gliner2 import GLiNER2  # pyrefly: ignore[missing-import]  # noqa: E402


class Gliner2Detector(BaseNERDetector):
    """Detect PII with a GLiNER2 model.

    labels is required, because GLiNER2 is queried with the internal labels. A
    str model is loaded with GLiNER2.from_pretrained; a loaded instance is used
    as-is.
    """

    def __init__(
        self,
        model: GLiNER2 | str,
        labels: list[str] | dict[str, str],
        threshold: float = 0.5,
        max_concurrency: int | None = None,
    ) -> None:
        """Store or load the model, then set the labels and threshold."""
        super().__init__(labels, max_concurrency=max_concurrency)
        self.model = (
            GLiNER2.from_pretrained(model) if isinstance(model, str) else model
        )
        self.threshold = threshold

    async def _raw_detect(self, text: str) -> list[Detection]:
        """Run GLiNER2 and build one detection per entity, native labels kept."""
        result = await self._run_blocking(
            self.model.extract_entities,
            text,
            entity_types=self.internal_labels,
            threshold=self.threshold,
            include_spans=True,
            include_confidence=True,
        )
        detections: list[Detection] = []
        for native_label, entities in result["entities"].items():
            for entity in entities:
                span = Span(entity["start"], entity["end"])
                detections.append(
                    Detection(
                        span=span,
                        text=entity["text"],
                        label=native_label,
                        confidence=entity["confidence"],
                    )
                )
        return detections
```

Then rewrite `src/piighost/components/detector/ner/__init__.py` to expose the
adapter lazily. The full file becomes:

```python
"""NER detectors: model-backed adapters over a shared label-mapping base.

BaseNERDetector holds the shared logic and imports nothing optional. Concrete
model-backed adapters, each behind its own optional extra, are added here as
they land, exposed lazily so a missing extra fails only on access.
"""

from typing import Any

from piighost.components.detector.ner.base import BaseNERDetector

__all__ = ["BaseNERDetector", "Gliner2Detector"]


def __getattr__(name: str) -> Any:
    """Import a NER adapter on demand so its optional extra stays optional."""
    if name == "Gliner2Detector":
        from piighost.components.detector.ner.gliner2 import Gliner2Detector

        return Gliner2Detector

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

- [ ] **Step 4: Run tests and checks**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/components/detector/ner/test_gliner2.py tests/regression/test_imports.py -q`
Expected: the gliner2 tests SKIP (gliner2 absent); `test_imports.py` passes, its `test_every_module_imports_cleanly` importing `piighost.components.detector.ner.gliner2` raises ImportError mentioning `piighost[gliner2]`, which the walk tolerates.

Run: `uv run --no-sync ruff format src/piighost/components/detector/ner/gliner2.py tests/components/detector/ner/test_gliner2.py && uv run --no-sync ruff check src/piighost/components/detector/ner/gliner2.py && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean, pyrefly 0 errors (the `gliner2` import is suppressed).

- [ ] **Step 5: Commit**

```bash
git add src/piighost/components/detector/ner/gliner2.py src/piighost/components/detector/ner/__init__.py tests/components/detector/ner/test_gliner2.py
git commit -m "feat(detector): add the GLiNER2 detector"
```

---

### Task 4: SpacyDetector

**Files:**
- Create: `src/piighost/components/detector/ner/spacy.py`
- Modify: `src/piighost/components/detector/ner/__init__.py`
- Test: `tests/components/detector/ner/test_spacy.py`

- [ ] **Step 1: Write the tests**

Create `tests/components/detector/ner/test_spacy.py`:

```python
"""Tests for the SpacyDetector.

Conformance and mapping inject a fake spaCy doc (no model). The integration test
loads a real spaCy model and is marked integration. All skip when spacy absent.
"""

import pytest

from piighost.components.detector import AnyDetector


class _Ent:
    """A stand-in for a spaCy entity span."""

    def __init__(self, text: str, label: str, start_char: int, end_char: int) -> None:
        self.text = text
        self.label_ = label
        self.start_char = start_char
        self.end_char = end_char


class _Doc:
    """A stand-in for a spaCy Doc exposing ents."""

    def __init__(self, ents: list[_Ent]) -> None:
        self.ents = ents


class _FakeNlp:
    """A callable stand-in for a spaCy Language model."""

    def __init__(self, doc: _Doc) -> None:
        self._doc = doc

    def __call__(self, text: str) -> _Doc:
        return self._doc


class TestConformance:
    def test_satisfies_the_detector_port(self) -> None:
        """SpacyDetector built on an injected model is an AnyDetector."""
        pytest.importorskip("spacy")
        from piighost.components.detector.ner import SpacyDetector

        detector = SpacyDetector(model=_FakeNlp(_Doc([])))
        assert isinstance(detector, AnyDetector)


class TestDetect:
    async def test_keeps_every_entity_when_unmapped(self) -> None:
        """With no label map, every spaCy entity is kept with its native label."""
        pytest.importorskip("spacy")
        from piighost.components.detector.ner import SpacyDetector
        from piighost.models import Span

        doc = _Doc([_Ent("Emma", "PER", 0, 4)])
        detector = SpacyDetector(model=_FakeNlp(doc))
        detections = await detector.detect("Emma is here")
        assert len(detections) == 1
        assert detections[0].label == "PER"
        assert detections[0].span == Span(0, 4)
        assert detections[0].confidence == 1.0

    async def test_relabels_and_filters_with_a_map(self) -> None:
        """A label map relabels the kept entity and drops the unmapped one."""
        pytest.importorskip("spacy")
        from piighost.components.detector.ner import SpacyDetector

        doc = _Doc([_Ent("Emma", "PER", 0, 4), _Ent("here", "MISC", 8, 12)])
        detector = SpacyDetector(model=_FakeNlp(doc), labels={"PERSON": "PER"})
        detections = await detector.detect("Emma is here")
        assert [d.label for d in detections] == ["PERSON"]


@pytest.mark.integration
class TestIntegration:
    async def test_detects_a_person_with_a_real_model(self) -> None:
        """A real spaCy model finds a person in a simple sentence."""
        pytest.importorskip("spacy")
        spacy = pytest.importorskip("spacy")
        if not spacy.util.is_package("en_core_web_sm"):
            pytest.skip("en_core_web_sm model not installed")
        from piighost.components.detector.ner import SpacyDetector

        detector = SpacyDetector(model="en_core_web_sm", labels={"PERSON": "PERSON"})
        detections = await detector.detect("My name is Patrick.")
        assert any(d.label == "PERSON" for d in detections)
```

- [ ] **Step 2: Run it to verify current state**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/components/detector/ner/test_spacy.py -q`
Expected: all tests SKIP (spacy absent).

- [ ] **Step 3: Write the adapter**

Create `src/piighost/components/detector/ner/spacy.py`:

```python
"""spaCy detector (optional: spacy).

Wraps a spaCy Language model so a caller injects a loaded instance or passes a
model name to load. This module needs the spacy package; it is guarded so
importing it without the dependency raises an ImportError pointing at the extra.
"""

import importlib.util

from piighost.components.detector.ner.base import BaseNERDetector
from piighost.models import Detection, Span

if importlib.util.find_spec("spacy") is None:
    raise ImportError(
        "SpacyDetector requires the spacy package. "
        "Install it with: pip install piighost[spacy]"
    )

import spacy  # pyrefly: ignore[missing-import]  # noqa: E402
from spacy.language import Language  # pyrefly: ignore[missing-import]  # noqa: E402


class SpacyDetector(BaseNERDetector):
    """Detect PII with a spaCy NER model.

    labels is optional. When omitted, every entity spaCy produces is kept with
    its spaCy label. A str model is loaded with spacy.load; a loaded instance is
    used as-is.
    """

    def __init__(
        self,
        model: Language | str,
        labels: list[str] | dict[str, str] | None = None,
        max_concurrency: int | None = None,
    ) -> None:
        """Store or load the model, then set the labels."""
        super().__init__(labels, max_concurrency=max_concurrency)
        self.model = spacy.load(model) if isinstance(model, str) else model

    async def _raw_detect(self, text: str) -> list[Detection]:
        """Run spaCy and build one detection per entity, native labels kept."""
        doc = await self._run_blocking(self.model, text)
        detections: list[Detection] = []
        for entity in doc.ents:
            span = Span(entity.start_char, entity.end_char)
            detections.append(
                Detection(
                    span=span,
                    text=entity.text,
                    label=entity.label_,
                    confidence=1.0,
                )
            )
        return detections
```

Then rewrite `src/piighost/components/detector/ner/__init__.py` to add the spaCy
adapter's lazy branch. The full file becomes:

```python
"""NER detectors: model-backed adapters over a shared label-mapping base.

BaseNERDetector holds the shared logic and imports nothing optional. Concrete
model-backed adapters, each behind its own optional extra, are added here as
they land, exposed lazily so a missing extra fails only on access.
"""

from typing import Any

from piighost.components.detector.ner.base import BaseNERDetector

__all__ = ["BaseNERDetector", "Gliner2Detector", "SpacyDetector"]


def __getattr__(name: str) -> Any:
    """Import a NER adapter on demand so its optional extra stays optional."""
    if name == "Gliner2Detector":
        from piighost.components.detector.ner.gliner2 import Gliner2Detector

        return Gliner2Detector
    if name == "SpacyDetector":
        from piighost.components.detector.ner.spacy import SpacyDetector

        return SpacyDetector

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

- [ ] **Step 4: Run tests and checks**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/components/detector/ner/test_spacy.py tests/regression/test_imports.py -q`
Expected: spacy tests SKIP; `test_imports.py` passes (the walk tolerates the `piighost[spacy]` ImportError).

Run: `uv run --no-sync ruff format src/piighost/components/detector/ner/spacy.py tests/components/detector/ner/test_spacy.py && uv run --no-sync ruff check src/piighost/components/detector/ner/spacy.py && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean, pyrefly 0 errors.

- [ ] **Step 5: Commit**

```bash
git add src/piighost/components/detector/ner/spacy.py src/piighost/components/detector/ner/__init__.py tests/components/detector/ner/test_spacy.py
git commit -m "feat(detector): add the spaCy detector"
```

---

### Task 5: TransformersDetector

**Files:**
- Create: `src/piighost/components/detector/ner/transformers.py`
- Modify: `src/piighost/components/detector/ner/__init__.py`
- Test: `tests/components/detector/ner/test_transformers.py`

- [ ] **Step 1: Write the tests**

Create `tests/components/detector/ner/test_transformers.py`:

```python
"""Tests for the TransformersDetector.

Conformance and mapping inject a fake pipeline (no download). The integration
test loads a real HF pipeline and is marked integration. All skip when
transformers is absent.
"""

import pytest

from piighost.components.detector import AnyDetector


class _FakePipeline:
    """A callable stand-in returning HF token-classification dicts."""

    def __init__(self, entities: list[dict]) -> None:
        self._entities = entities

    def __call__(self, text: str) -> list[dict]:
        return self._entities


class TestConformance:
    def test_satisfies_the_detector_port(self) -> None:
        """TransformersDetector built on an injected pipeline is an AnyDetector."""
        pytest.importorskip("transformers")
        from piighost.components.detector.ner import TransformersDetector

        detector = TransformersDetector(pipeline=_FakePipeline([]))
        assert isinstance(detector, AnyDetector)


class TestDetect:
    async def test_builds_detection_from_pipeline_output(self) -> None:
        """A pipeline entity becomes a Detection with span, text, confidence."""
        pytest.importorskip("transformers")
        from piighost.components.detector.ner import TransformersDetector
        from piighost.models import Span

        entities = [
            {"entity_group": "PER", "score": 0.99, "start": 0, "end": 4}
        ]
        detector = TransformersDetector(pipeline=_FakePipeline(entities))
        detections = await detector.detect("Emma is here")
        assert len(detections) == 1
        assert detections[0].label == "PER"
        assert detections[0].span == Span(0, 4)
        assert detections[0].text == "Emma"
        assert detections[0].confidence == pytest.approx(0.99)

    async def test_drops_entities_below_threshold(self) -> None:
        """An entity scoring below the threshold is dropped."""
        pytest.importorskip("transformers")
        from piighost.components.detector.ner import TransformersDetector

        entities = [{"entity_group": "PER", "score": 0.10, "start": 0, "end": 4}]
        detector = TransformersDetector(pipeline=_FakePipeline(entities), threshold=0.5)
        assert await detector.detect("Emma is here") == []


@pytest.mark.integration
class TestIntegration:
    async def test_detects_a_person_with_a_real_pipeline(self) -> None:
        """A real HF NER pipeline finds a person in a simple sentence."""
        pytest.importorskip("transformers")
        from piighost.components.detector.ner import TransformersDetector

        detector = TransformersDetector(pipeline="dslim/bert-base-NER")
        detections = await detector.detect("My name is Patrick.")
        assert any(d.text for d in detections)
```

- [ ] **Step 2: Run it to verify current state**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/components/detector/ner/test_transformers.py -q`
Expected: all tests SKIP (transformers absent).

- [ ] **Step 3: Write the adapter**

Create `src/piighost/components/detector/ner/transformers.py`:

```python
"""Transformers detector (optional: transformers).

Wraps a Hugging Face token-classification pipeline so a caller injects a built
pipeline or passes a model name to load. This module needs the transformers
package; it is guarded so importing it without the dependency raises an
ImportError pointing at the extra.
"""

import importlib.util

from piighost.components.detector.ner.base import BaseNERDetector
from piighost.models import Detection, Span

if importlib.util.find_spec("transformers") is None:
    raise ImportError(
        "TransformersDetector requires the transformers package. "
        "Install it with: pip install piighost[transformers]"
    )

from transformers.pipelines.token_classification import (  # pyrefly: ignore[missing-import]  # noqa: E402
    TokenClassificationPipeline,
)


class TransformersDetector(BaseNERDetector):
    """Detect PII with a Hugging Face token-classification pipeline.

    labels is optional. When omitted, every entity is kept with its model-native
    label. A str pipeline is loaded with the transformers pipeline factory as an
    ner pipeline; a built pipeline is used as-is. An entity scoring below
    threshold is dropped.
    """

    def __init__(
        self,
        pipeline: TokenClassificationPipeline | str,
        labels: list[str] | dict[str, str] | None = None,
        threshold: float = 0.0,
        max_concurrency: int | None = None,
    ) -> None:
        """Store or build the pipeline, then set the labels and threshold."""
        super().__init__(labels, max_concurrency=max_concurrency)
        if isinstance(pipeline, str):
            from transformers import (  # pyrefly: ignore[missing-import]
                pipeline as hf_pipeline,
            )

            pipeline = hf_pipeline("ner", model=pipeline)
        self.pipeline = pipeline
        self.threshold = threshold

    async def _raw_detect(self, text: str) -> list[Detection]:
        """Run the pipeline and build detections, dropping sub-threshold ones."""
        results = await self._run_blocking(self.pipeline, text)
        detections: list[Detection] = []
        for entity in results:
            score = float(entity["score"])
            if score < self.threshold:
                continue
            native_label = entity.get("entity_group", entity.get("entity", "UNKNOWN"))
            start = int(entity["start"])
            end = int(entity["end"])
            span = Span(start, end)
            detections.append(
                Detection(
                    span=span,
                    text=text[start:end],
                    label=native_label,
                    confidence=score,
                )
            )
        return detections
```

Then rewrite `src/piighost/components/detector/ner/__init__.py` to add the
transformers adapter's lazy branch. The full, final file becomes:

```python
"""NER detectors: model-backed adapters over a shared label-mapping base.

BaseNERDetector holds the shared logic and imports nothing optional. Concrete
model-backed adapters, each behind its own optional extra, are added here as
they land, exposed lazily so a missing extra fails only on access.
"""

from typing import Any

from piighost.components.detector.ner.base import BaseNERDetector

__all__ = [
    "BaseNERDetector",
    "Gliner2Detector",
    "SpacyDetector",
    "TransformersDetector",
]


def __getattr__(name: str) -> Any:
    """Import a NER adapter on demand so its optional extra stays optional."""
    if name == "Gliner2Detector":
        from piighost.components.detector.ner.gliner2 import Gliner2Detector

        return Gliner2Detector
    if name == "SpacyDetector":
        from piighost.components.detector.ner.spacy import SpacyDetector

        return SpacyDetector
    if name == "TransformersDetector":
        from piighost.components.detector.ner.transformers import (
            TransformersDetector,
        )

        return TransformersDetector

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

- [ ] **Step 4: Run tests and checks**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/components/detector/ner/test_transformers.py tests/regression/test_imports.py -q`
Expected: transformers tests SKIP; `test_imports.py` passes.

Run: `uv run --no-sync ruff format src/piighost/components/detector/ner/transformers.py tests/components/detector/ner/test_transformers.py && uv run --no-sync ruff check src/piighost/components/detector/ner/transformers.py && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean, pyrefly 0 errors.

- [ ] **Step 5: Commit**

```bash
git add src/piighost/components/detector/ner/transformers.py src/piighost/components/detector/ner/__init__.py tests/components/detector/ner/test_transformers.py
git commit -m "feat(detector): add the transformers detector"
```

---

### Task 6: Regression guard and full verification

**Files:**
- Modify: `tests/regression/test_imports.py`

- [ ] **Step 1: Add BaseNERDetector to the public-API guard**

In `tests/regression/test_imports.py`, in the `PUBLIC_API` list, after the line `("piighost.components.detector", "CompositeDetector"),` add:

```python
    ("piighost.components.detector.ner", "BaseNERDetector"),
```

Do NOT add the three adapters: a `hasattr` probe would trigger their lazy import and fail when the extra is absent. Their import behavior is covered by `test_every_module_imports_cleanly`.

- [ ] **Step 2: Run the regression guard**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/regression/test_imports.py -q`
Expected: PASS. The new `BaseNERDetector` case resolves; the walk tolerates the three adapters' `piighost[...]` ImportErrors.

- [ ] **Step 3: Run the full default suite**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest -q`
Expected: PASS. The NER conformance/integration tests skip (extras absent); everything else is green.

- [ ] **Step 4: Confirm the integration tests collect and skip cleanly**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest -m integration tests/components/detector/ner -q`
Expected: the integration tests are collected and reported as skipped (not errored), because the extras are absent.

- [ ] **Step 5: Run lint and type checks**

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean, pyrefly 0 errors under `src/piighost`.

- [ ] **Step 6: Commit**

```bash
git add tests/regression/test_imports.py
git commit -m "test(detector): guard the BaseNERDetector public symbol"
```

---

## Notes for the implementer

- gliner2 / spacy / transformers / torch are deliberately NOT in the dev venv. Do not install them. The adapter modules must type-check (pyrefly 0) via the `# pyrefly: ignore[missing-import]` suppressions, and their tests must skip via `pytest.importorskip`.
- The base (Task 2) is where the shared logic lives and is fully unit-tested without a model; that is the real verification. The adapters are thin and their fake-model tests skip locally, so lean on the base tests, the import-guard walk, and pyrefly/ruff to judge correctness.
- Do not add `from_config` or any config model; the `model | str` constructor absorbs model loading, and the config block comes later.
- `flat_ner` from v1 is intentionally dropped (it was stored but never used).
- Keep `components/detector/__init__.py` unchanged; the NER family is reached via `piighost.components.detector.ner`.
