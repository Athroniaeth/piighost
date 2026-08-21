# Presidio detector adapter: design

**Date:** 2026-08-21
**Status:** approved
**Roadmap item:** "Presidio detector adapter" (docs/en|fr/roadmap.md)

## Goal

Let a caller reuse Microsoft Presidio's recognizers inside a piighost pipeline. A
`PresidioDetector` wraps a Presidio `AnalyzerEngine` behind the `AnyDetector`
port, so Presidio finds the spans while piighost keeps its own entity linking,
conversation memory, and placeholder factories. The adapter is usable both
programmatically (inject an engine) and from a TOML/JSON config.

## Scope

- v1 is **complete**: the adapter plus a config model, chosen over injection-only.
- Programmatic use injects a constructed `AnalyzerEngine`. There is no
  "model string to load" path, because unlike a single NER model, an
  `AnalyzerEngine` is assembled from an NLP engine plus a recognizer registry.
- The config path builds Presidio's **default** `AnalyzerEngine` (default English
  NLP engine and default recognizers). Other languages, custom recognizers, or a
  custom NLP engine are the programmatic path. This boundary is deliberate.

## Approach

`PresidioDetector` extends `BaseNERDetector`. Presidio's results carry an
`entity_type`, a `start`/`end`, and a `score`, which map directly onto the
`_raw_detect` hook, and `BaseNERDetector` then applies the shared external-to-native
label mapping and filtering, exactly as `Gliner2Detector`, `SpacyDetector`, and
`TransformersDetector` do. It lives in the `ner/` package with those siblings,
because it extends their label-mapping base; the `ner` base is really a
label-mapping template, so a recognizer-backed adapter fits even though Presidio
is broader than a single NER model.

Rejected alternatives:

- A standalone detector implementing `AnyDetector` directly. Rejected: it would
  reimplement the label mapping `BaseNERDetector` already provides.
- Placing it at top-level `detector/presidio.py`. Rejected: it extends
  `BaseNERDetector`, so its place is beside its siblings in `ner/`.

## Components

### 1. `src/piighost/components/detector/ner/presidio.py` (extra: `presidio`)

Module-level guard, matching `gliner2.py`:

```python
if importlib.util.find_spec("presidio_analyzer") is None:
    raise ImportError(
        "PresidioDetector requires the presidio-analyzer package. "
        "Install it with: pip install piighost[presidio]"
    )

from presidio_analyzer import AnalyzerEngine  # pyrefly: ignore[missing-import]  # noqa: E402
```

`PresidioDetector(BaseNERDetector)`:

- `__init__(self, analyzer: AnalyzerEngine, labels: list[str] | dict[str, str] | None = None, language: str = "en", threshold: float = 0.0, max_concurrency: int | None = None)`.
  - Calls `super().__init__(labels, max_concurrency=max_concurrency)`.
  - Stores `analyzer`, `language`, `threshold`.
- `_raw_detect(self, text)`:
  - `results = await self._run_blocking(self.analyzer.analyze, text, language=self.language, entities=self.internal_labels or None, score_threshold=self.threshold)`.
  - Build one `Detection` per result: `label=result.entity_type`,
    `span=Span(result.start, result.end)`, `text=text[result.start:result.end]`,
    `confidence=result.score`.
  - `entities=self.internal_labels or None` restricts Presidio to the queried
    labels when a map is given, or asks for all when the map is empty.

### 2. `src/piighost/components/detector/ner/__init__.py`

Add `"PresidioDetector"` to `__all__` and a `__getattr__` branch importing it from
`.presidio`, following the existing lazy pattern.

### 3. `src/piighost/config/models/detector_model.py`

```python
class PresidioDetectorConfig(_ComponentConfig):
    """Config for the Presidio detector, wrapping a default AnalyzerEngine."""

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

### 4. `src/piighost/config/models/detector.py`

Import `PresidioDetectorConfig` and add it to the discriminated union alongside
`Gliner2DetectorConfig`, `SpacyDetectorConfig`, and `TransformersDetectorConfig`.

### 5. `pyproject.toml`

Add `presidio = ["presidio-analyzer>=2.2"]` to the optional dependencies, and add
`presidio-analyzer` to the `all` extra. presidio-analyzer pulls spaCy; the default
engine needs a spaCy model installed, which is the caller's setup step, documented.

## Data flow

text -> `PresidioDetector._raw_detect` -> `analyzer.analyze` (off the event loop via
`_run_blocking`, bounded by `max_concurrency`) -> `RecognizerResult`s ->
`Detection`s with native labels -> `BaseNERDetector.detect` maps and filters by the
label map -> the rest of the pipeline links, remembers, and anonymizes as usual.

## Error handling

- Importing the module without the extra raises `ImportError` naming
  `piighost[presidio]` (module-level guard).
- `PresidioDetectorConfig.build()` without the extra surfaces the same
  `ImportError` through its lazy import, matching the other model configs.
- No spaCy model for the default engine surfaces Presidio's own error at
  `AnalyzerEngine()` construction. Documented, not caught.

## Testing

- `tests/components/detector/ner/test_presidio.py`, guarded by
  `pytest.importorskip("presidio_analyzer")`. A `_FakeAnalyzer` exposes
  `analyze(self, text, language, entities, score_threshold) -> list[_Result]`
  where `_Result` carries `entity_type`, `start`, `end`, `score`, so no engine is
  built and no spaCy model is downloaded. Cases:
  - conformance: a `PresidioDetector` on a fake analyzer is an `AnyDetector`.
  - relabel: a native `PERSON` result maps to the external label under a map.
  - filter: a native label absent from the map is dropped.
  - the queried `internal_labels` are passed to `analyze` as `entities`.
  - the `threshold` is passed as `score_threshold`.
- `tests/config/`: a `PresidioDetectorConfig.build()` test that monkeypatches
  `presidio_analyzer.AnalyzerEngine` with a fake, so no spaCy model is needed,
  asserting the result is a `PresidioDetector` wired with the configured labels,
  language, and threshold.
- `tests/regression/test_imports.py` auto-covers the optional-extra guard.

## Documentation

- `docs/en/reference/detectors.md` and `docs/fr/reference/detectors.md`: a
  `### PresidioDetector` section next to the other NER detectors, the import in
  the detector import block, and a config-type note. Code blocks stay
  byte-identical between EN and FR.
- `docs/en/roadmap.md` and `docs/fr/roadmap.md`: remove the "Presidio detector
  adapter" section (now shipped) and add it to the shipped list in the intro
  paragraph.

## Out of scope

- Building non-default `AnalyzerEngine`s from config (custom recognizers, NLP
  engines, multi-language). Programmatic path only.
- Any change to the linking, memory, or placeholder stages. The adapter is a
  detector only.
