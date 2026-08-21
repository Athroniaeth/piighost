# Presidio Detector Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap a Presidio `AnalyzerEngine` behind the `AnyDetector` port so callers reuse Presidio recognizers inside a piighost pipeline, usable programmatically and from a TOML/JSON config.

**Architecture:** `PresidioDetector` extends `BaseNERDetector`; Presidio's `entity_type`/`start`/`end`/`score` results map onto the `_raw_detect` hook, and the base handles label mapping and filtering. A `PresidioDetectorConfig` builds Presidio's default `AnalyzerEngine` for the config path. The module is guarded behind a new `presidio` optional extra.

**Tech Stack:** Python 3.11+, presidio-analyzer, pydantic (config), pytest (asyncio auto mode), uv, ruff, pyrefly, bandit.

**Spec:** `docs/superpowers/specs/2026-08-21-presidio-detector-adapter-design.md`

---

## File Structure

- `pyproject.toml` — add the `presidio` optional extra, the `presidio` dependency-group, and `presidio-analyzer` to `all`.
- `src/piighost/components/detector/ner/presidio.py` (create) — the guarded `PresidioDetector` adapter.
- `src/piighost/components/detector/ner/__init__.py` (modify) — lazy export.
- `src/piighost/config/models/detector_model.py` (modify) — `PresidioDetectorConfig`.
- `src/piighost/config/models/detector.py` (modify) — add the config to the discriminated union.
- `tests/components/detector/ner/test_presidio.py` (create) — adapter tests, fake analyzer.
- `tests/config/test_presidio_detector.py` (create) — config build test, faked engine.
- `docs/en/reference/detectors.md`, `docs/fr/reference/detectors.md` (modify) — reference section.
- `docs/en/roadmap.md`, `docs/fr/roadmap.md` (modify) — drop the shipped roadmap item.

Run adapter/config tests with the extra installed: `uv run --group presidio pytest <path>`. The default `uv run pytest` skips them via `importorskip`, matching gliner2/spacy/transformers.

---

## Task 1: Add the `presidio` optional extra and dependency-group

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the `presidio` optional extra**

In `pyproject.toml`, under `[project.optional-dependencies]`, add the block after the `mistral` entry:

```toml
presidio = [
    "presidio-analyzer>=2.2",
]
```

- [ ] **Step 2: Add `presidio-analyzer` to the `all` extra**

Change the `all` extra so its `piighost[...]` list ends with `,presidio]`:

```toml
all = [
    "piighost[gliner2,redis,middleware,pydantic-ai,client,spacy,transformers,llm,observation,fuzzy,config,argon2,crypto,mistral,sqlalchemy,presidio]",
]
```

- [ ] **Step 3: Add the `presidio` dependency-group**

In `pyproject.toml`, under `[dependency-groups]`, add after the `gliner2` group:

```toml
presidio = [
    "presidio-analyzer>=2.2",
]
```

- [ ] **Step 4: Update the lockfile**

Run: `uv lock`
Expected: `uv.lock` is rewritten and now contains `presidio-analyzer` (and its transitive deps). This keeps `uv sync --locked` (used by CI) passing.

- [ ] **Step 5: Verify the group installs and imports**

Run: `uv run --group presidio python -c "import presidio_analyzer; from presidio_analyzer import AnalyzerEngine; print('ok')"`
Expected: prints `ok` (installs presidio-analyzer + spaCy the first time; no model download because no engine is constructed).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add the presidio optional extra"
```

---

## Task 2: `PresidioDetector` adapter

**Files:**
- Create: `src/piighost/components/detector/ner/presidio.py`
- Modify: `src/piighost/components/detector/ner/__init__.py`
- Test: `tests/components/detector/ner/test_presidio.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/components/detector/ner/test_presidio.py`:

```python
"""Tests for the PresidioDetector adapter.

A fake analyzer is injected, so presidio-analyzer is imported but no engine is
built and no spaCy model is downloaded; they skip when presidio is absent.
"""

import pytest

from piighost.components.detector import AnyDetector


class _Result:
    """A stand-in for a Presidio RecognizerResult."""

    def __init__(self, entity_type: str, start: int, end: int, score: float) -> None:
        self.entity_type = entity_type
        self.start = start
        self.end = end
        self.score = score


class _FakeAnalyzer:
    """A stand-in AnalyzerEngine recording its call and returning fixed results."""

    def __init__(self, results: list[_Result] | None = None) -> None:
        self._results = results or []
        self.calls: list[dict[str, object]] = []

    def analyze(
        self,
        text: str,
        language: str = "en",
        entities: list[str] | None = None,
        score_threshold: float | None = None,
    ) -> list[_Result]:
        self.calls.append(
            {
                "text": text,
                "language": language,
                "entities": entities,
                "score_threshold": score_threshold,
            }
        )
        return self._results


class TestConformance:
    def test_satisfies_the_detector_port(self) -> None:
        """A PresidioDetector on an injected analyzer is an AnyDetector."""
        pytest.importorskip("presidio_analyzer")
        from piighost.components.detector.ner import PresidioDetector

        detector = PresidioDetector(analyzer=_FakeAnalyzer())
        assert isinstance(detector, AnyDetector)


class TestDetect:
    async def test_builds_a_detection_per_result(self) -> None:
        """Each Presidio result becomes a Detection with its span text."""
        pytest.importorskip("presidio_analyzer")
        from piighost.components.detector.ner import PresidioDetector

        analyzer = _FakeAnalyzer([_Result("PERSON", 0, 4, 0.9)])
        detector = PresidioDetector(analyzer=analyzer, labels=["PERSON"])
        detections = await detector.detect("Emma is here")
        assert len(detections) == 1
        assert detections[0].label == "PERSON"
        assert detections[0].text == "Emma"
        assert detections[0].confidence == 0.9

    async def test_relabels_a_native_type_to_the_external_label(self) -> None:
        """A native PERSON type is relabeled to the mapped external label."""
        pytest.importorskip("presidio_analyzer")
        from piighost.components.detector.ner import PresidioDetector

        analyzer = _FakeAnalyzer([_Result("PERSON", 0, 4, 0.9)])
        detector = PresidioDetector(analyzer=analyzer, labels={"NAME": "PERSON"})
        detections = await detector.detect("Emma is here")
        assert len(detections) == 1
        assert detections[0].label == "NAME"

    async def test_drops_an_unmapped_type(self) -> None:
        """A native type absent from a non-empty map is dropped."""
        pytest.importorskip("presidio_analyzer")
        from piighost.components.detector.ner import PresidioDetector

        analyzer = _FakeAnalyzer([_Result("US_SSN", 0, 3, 0.9)])
        detector = PresidioDetector(analyzer=analyzer, labels={"NAME": "PERSON"})
        detections = await detector.detect("123 is here")
        assert detections == []

    async def test_passes_internal_labels_and_threshold_to_analyze(self) -> None:
        """The queried internal labels and threshold reach analyze."""
        pytest.importorskip("presidio_analyzer")
        from piighost.components.detector.ner import PresidioDetector

        analyzer = _FakeAnalyzer()
        detector = PresidioDetector(
            analyzer=analyzer, labels={"NAME": "PERSON"}, threshold=0.4
        )
        await detector.detect("Emma is here")
        assert analyzer.calls[0]["entities"] == ["PERSON"]
        assert analyzer.calls[0]["score_threshold"] == 0.4

    async def test_queries_all_entities_when_no_labels(self) -> None:
        """With no label map, analyze is asked for all entities (None)."""
        pytest.importorskip("presidio_analyzer")
        from piighost.components.detector.ner import PresidioDetector

        analyzer = _FakeAnalyzer()
        detector = PresidioDetector(analyzer=analyzer)
        await detector.detect("Emma is here")
        assert analyzer.calls[0]["entities"] is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --group presidio pytest tests/components/detector/ner/test_presidio.py -v`
Expected: FAIL with an `ImportError`/`AttributeError` for `PresidioDetector` (module does not exist yet).

- [ ] **Step 3: Create the adapter**

Create `src/piighost/components/detector/ner/presidio.py`:

```python
"""Presidio detector (optional: presidio).

Wraps a Presidio AnalyzerEngine so a caller reuses Presidio's recognizers inside
a piighost pipeline. This module needs the presidio-analyzer package; it is
guarded so importing it without the dependency raises an ImportError pointing at
the extra.
"""

import importlib.util

from piighost.components.detector.ner.base import BaseNERDetector
from piighost.models import Detection, Span

if importlib.util.find_spec("presidio_analyzer") is None:
    raise ImportError(
        "PresidioDetector requires the presidio-analyzer package. "
        "Install it with: pip install piighost[presidio]"
    )

from presidio_analyzer import AnalyzerEngine  # pyrefly: ignore[missing-import]  # noqa: E402


class PresidioDetector(BaseNERDetector):
    """Detect PII with a Presidio AnalyzerEngine.

    The analyzer is injected, because an AnalyzerEngine is assembled from an NLP
    engine and a recognizer registry rather than loaded from a single model
    name. Presidio returns an entity type, a span, and a score per finding,
    which the base class then maps and filters through the labels argument.

    Attributes:
        analyzer: The Presidio AnalyzerEngine queried for entities.
        language: The language code passed to analyze.
        threshold: The score at or above which Presidio keeps a finding.
    """

    def __init__(
        self,
        analyzer: AnalyzerEngine,
        labels: list[str] | dict[str, str] | None = None,
        language: str = "en",
        threshold: float = 0.0,
        max_concurrency: int | None = None,
    ) -> None:
        """Store the analyzer, then set the labels, language, and threshold."""
        super().__init__(labels, max_concurrency=max_concurrency)
        self.analyzer = analyzer
        self.language = language
        self.threshold = threshold

    async def _raw_detect(self, text: str) -> list[Detection]:
        """Run Presidio and build one detection per finding, native types kept."""
        results = await self._run_blocking(
            self.analyzer.analyze,
            text,
            language=self.language,
            entities=self.internal_labels or None,
            score_threshold=self.threshold,
        )
        detections: list[Detection] = []
        for result in results:
            span = Span(result.start, result.end)
            detection = Detection(
                span=span,
                text=text[result.start : result.end],
                label=result.entity_type,
                confidence=result.score,
            )
            detections.append(detection)
        return detections
```

- [ ] **Step 4: Add the lazy export**

In `src/piighost/components/detector/ner/__init__.py`, add `"PresidioDetector"` to `__all__` (after `"Gliner2PiiDetector"`):

```python
__all__ = [
    "BaseNERDetector",
    "Gliner2Detector",
    "Gliner2PiiDetector",
    "PresidioDetector",
    "SpacyDetector",
    "TransformersDetector",
]
```

And add a `__getattr__` branch (after the `Gliner2PiiDetector` branch):

```python
    if name == "PresidioDetector":
        from piighost.components.detector.ner.presidio import PresidioDetector

        return PresidioDetector
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --group presidio pytest tests/components/detector/ner/test_presidio.py -v`
Expected: PASS (5 passed).

- [ ] **Step 6: Lint**

Run: `make lint`
Expected: passes. (`make lint` runs in the default env where presidio-analyzer is absent, so pyrefly does not type-check `presidio.py`; the `# pyrefly: ignore[missing-import]` guards the annotation regardless.)

- [ ] **Step 7: Commit**

```bash
git add src/piighost/components/detector/ner/presidio.py src/piighost/components/detector/ner/__init__.py tests/components/detector/ner/test_presidio.py
git commit -m "feat(detector): add the Presidio detector adapter"
```

---

## Task 3: `PresidioDetectorConfig`

**Files:**
- Modify: `src/piighost/config/models/detector_model.py`
- Modify: `src/piighost/config/models/detector.py`
- Test: `tests/config/test_presidio_detector.py`

- [ ] **Step 1: Write the failing test**

Create `tests/config/test_presidio_detector.py`:

```python
"""Tests for the Presidio detector config.

The AnalyzerEngine is faked via monkeypatch, so build() constructs no real
engine and downloads no spaCy model; they skip when presidio is absent.
"""

import pytest


class _FakeEngine:
    """A stand-in AnalyzerEngine that records construction."""


def test_builds_a_presidio_detector(monkeypatch: pytest.MonkeyPatch) -> None:
    """The config wires labels, language, and threshold into a PresidioDetector."""
    pytest.importorskip("presidio_analyzer")
    monkeypatch.setattr("presidio_analyzer.AnalyzerEngine", _FakeEngine)

    from piighost.components.detector.ner import PresidioDetector
    from piighost.config.models.detector_model import PresidioDetectorConfig

    config = PresidioDetectorConfig(
        type="presidio",
        labels={"NAME": "PERSON"},
        language="en",
        threshold=0.3,
    )
    detector = config.build()

    assert isinstance(detector, PresidioDetector)
    assert isinstance(detector.analyzer, _FakeEngine)
    assert detector.language == "en"
    assert detector.threshold == 0.3
    assert detector.external_labels == ["NAME"]


def test_defaults_language_and_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    """Language defaults to en and threshold to 0.0 when omitted."""
    pytest.importorskip("presidio_analyzer")
    monkeypatch.setattr("presidio_analyzer.AnalyzerEngine", _FakeEngine)

    from piighost.config.models.detector_model import PresidioDetectorConfig

    config = PresidioDetectorConfig(type="presidio")
    detector = config.build()

    assert detector.language == "en"
    assert detector.threshold == 0.0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --group presidio pytest tests/config/test_presidio_detector.py -v`
Expected: FAIL with an `ImportError` for `PresidioDetectorConfig` (not defined yet).

- [ ] **Step 3: Add the config model**

In `src/piighost/config/models/detector_model.py`, add after `TransformersDetectorConfig` (before `LLMDetectorConfig`):

```python
class PresidioDetectorConfig(_ComponentConfig):
    """Config for the Presidio detector, wrapping a default AnalyzerEngine.

    The config path builds Presidio's default English AnalyzerEngine with its
    default recognizers. Other languages, custom recognizers, or a custom NLP
    engine are the programmatic path, constructing the engine and passing it to
    PresidioDetector directly.
    """

    type: Literal["presidio"]
    labels: list[str] | dict[str, str] | None = None
    language: str = "en"
    threshold: float = Field(default=0.0, ge=0.0, le=1.0)

    def build(self) -> AnyDetector:
        """Build a PresidioDetector over Presidio's default AnalyzerEngine."""
        from presidio_analyzer import AnalyzerEngine

        from piighost.components.detector.ner.presidio import PresidioDetector

        analyzer = AnalyzerEngine()
        return PresidioDetector(
            analyzer=analyzer,
            labels=self.labels,
            language=self.language,
            threshold=self.threshold,
        )
```

- [ ] **Step 4: Add the config to the discriminated union**

In `src/piighost/config/models/detector.py`, add `PresidioDetectorConfig` to the import from `detector_model`:

```python
from piighost.config.models.detector_model import (
    Gliner2DetectorConfig,
    LLMDetectorConfig,
    PresidioDetectorConfig,
    SpacyDetectorConfig,
    TransformersDetectorConfig,
)
```

And add it to the `DetectorConfig` union (after `TransformersDetectorConfig`):

```python
DetectorConfig = Annotated[
    RegexDetectorConfig
    | CompositeDetectorConfig
    | ExactMatchDetectorConfig
    | ChunkedDetectorConfig
    | Gliner2DetectorConfig
    | SpacyDetectorConfig
    | TransformersDetectorConfig
    | PresidioDetectorConfig
    | LLMDetectorConfig,
    Discriminator("type"),
]
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run --group presidio pytest tests/config/test_presidio_detector.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Run the full default suite and lint**

Run: `uv run pytest -q && make lint`
Expected: all pass; the presidio adapter/config tests skip in the default env, everything else is green.

- [ ] **Step 7: Commit**

```bash
git add src/piighost/config/models/detector_model.py src/piighost/config/models/detector.py tests/config/test_presidio_detector.py
git commit -m "feat(config): add PresidioDetectorConfig"
```

---

## Task 4: Documentation

**Files:**
- Modify: `docs/en/reference/detectors.md`, `docs/fr/reference/detectors.md`
- Modify: `docs/en/roadmap.md`, `docs/fr/roadmap.md`

- [ ] **Step 1: Add the import to the detectors reference (EN)**

In `docs/en/reference/detectors.md`, in the `from piighost.components.detector.ner import (...)` block, add `PresidioDetector` after `Gliner2PiiDetector`:

```python
from piighost.components.detector.ner import (
    Gliner2Detector,
    Gliner2PiiDetector,
    PresidioDetector,
    SpacyDetector,
    TransformersDetector,
)
```

- [ ] **Step 2: Add the reference section (EN)**

In `docs/en/reference/detectors.md`, add after the `TransformersDetector` section (before `### Label mapping`):

````markdown
### `PresidioDetector`

Wraps a Presidio `AnalyzerEngine` so a caller reuses Presidio's recognizers. Needs the `presidio` extra. The analyzer is injected, since an engine is assembled from an NLP engine and a recognizer registry, not loaded from a name. `labels` is optional, kept native when omitted. An entity scoring below `threshold` is dropped by Presidio.

```python
PresidioDetector(
    analyzer: AnalyzerEngine,
    labels: list[str] | dict[str, str] | None = None,
    language: str = "en",
    threshold: float = 0.0,
    max_concurrency: int | None = None,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `analyzer` | `AnalyzerEngine` | A constructed Presidio analyzer (required) |
| `labels` | `list[str] \| dict[str, str] \| None` | The labels to map and filter, or `None` to keep every native type |
| `language` | `str` | The language code passed to `analyze` |
| `threshold` | `float` | The score below which a finding is dropped |
| `max_concurrency` | `int \| None` | Cap on concurrent inferences, or `None` for unbounded |

From a config, the `presidio` detector type builds Presidio's default English `AnalyzerEngine`. For another language or custom recognizers, construct the engine yourself and use `PresidioDetector` directly.
````

- [ ] **Step 3: Mirror the import and section (FR)**

In `docs/fr/reference/detectors.md`, add `PresidioDetector` to the same import block (byte-identical code block), and add after the `TransformersDetector` section (before `### Label mapping`):

````markdown
### `PresidioDetector`

Enveloppe un `AnalyzerEngine` de Presidio pour réutiliser ses recognizers. A besoin de l'extra `presidio`. L'analyzer est injecté, car un moteur est assemblé d'un moteur NLP et d'un registre de recognizers, pas chargé depuis un nom. `labels` est optionnel, gardé natif quand il est omis. Une entité scorant sous `threshold` est écartée par Presidio.

```python
PresidioDetector(
    analyzer: AnalyzerEngine,
    labels: list[str] | dict[str, str] | None = None,
    language: str = "en",
    threshold: float = 0.0,
    max_concurrency: int | None = None,
)
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `analyzer` | `AnalyzerEngine` | Un analyzer Presidio construit (requis) |
| `labels` | `list[str] \| dict[str, str] \| None` | Les labels à mapper et filtrer, ou `None` pour garder chaque type natif |
| `language` | `str` | Le code de langue passé à `analyze` |
| `threshold` | `float` | Le score sous lequel une entité est écartée |
| `max_concurrency` | `int \| None` | Plafond d'inférences concurrentes, ou `None` pour sans limite |

Depuis une config, le type de détecteur `presidio` construit l'`AnalyzerEngine` anglais par défaut de Presidio. Pour une autre langue ou des recognizers custom, construisez le moteur vous-même et utilisez `PresidioDetector` directement.
````

- [ ] **Step 4: Drop the shipped roadmap item (EN)**

In `docs/en/roadmap.md`, delete the entire `## Presidio detector adapter` section (heading and its paragraph). The intro's "pluggable detectors" already covers it, so no intro edit.

- [ ] **Step 5: Drop the shipped roadmap item (FR)**

In `docs/fr/roadmap.md`, delete the entire `## Adaptateur détecteur Presidio` section (heading and its paragraph).

- [ ] **Step 6: Build both docs**

Run:
```bash
uv run zensical build --clean
uv run zensical build -f zensical.fr.toml
```
Expected: both builds succeed with no broken-link errors.

- [ ] **Step 7: Commit**

```bash
git add docs/en/reference/detectors.md docs/fr/reference/detectors.md docs/en/roadmap.md docs/fr/roadmap.md
git commit -m "docs(detectors): document the Presidio detector adapter (EN+FR)"
```

---

## Self-Review

**Spec coverage:**
- Adapter extending `BaseNERDetector`, injected analyzer, `_raw_detect` mapping → Task 2. ✓
- Lazy export → Task 2 Step 4. ✓
- `PresidioDetectorConfig` building the default engine, added to the union → Task 3. ✓
- `presidio` extra + `all` → Task 1. ✓
- Error handling (guarded import naming the extra) → Task 2 Step 3 (module guard); config surfaces it via lazy import in `build()`. ✓
- Testing (fake analyzer, five adapter cases + two config cases, regression auto-covers) → Tasks 2 and 3; regression `test_every_module_imports_cleanly` needs no change. ✓
- Docs (reference EN+FR, roadmap EN+FR) → Task 4. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code. ✓

**Type consistency:** `PresidioDetector(analyzer, labels=None, language="en", threshold=0.0, max_concurrency=None)` and the config fields (`type`, `labels`, `language`, `threshold`) are identical across Tasks 2, 3, and 4. `analyze(..., language=, entities=, score_threshold=)` matches between the adapter and the fake. `Detection(span=, text=, label=, confidence=)` and `Span(start, end)` match the codebase (`gliner2.py`). ✓
