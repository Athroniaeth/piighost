# Config Coverage B: Model Detectors and Catalogs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Widen the DetectorConfig union with exact, chunked, and the four model-backed detectors (gliner2, spacy, transformers, llm), and let a regex detector config pull the prebuilt pattern catalogs.

**Architecture:** Extend `config/models/detector.py` with the no-extra detectors (regex catalogs, exact, chunked) and add `config/models/detector_model.py` for the four extra-gated model detectors, each with a lazy build(). The union grows, so every nesting site (guard, override, composite, chunked) gains the new types for free.

**Tech Stack:** Python 3.11+, pydantic. Dev env lacks gliner2/spacy/transformers/torch and any llm provider package, so those detectors are tested at parse/dispatch level only.

---

## Conventions for every task

- Run with `uv run --no-sync`. Before each pytest run: `find src tests -name __pycache__ -type d -exec rm -rf {} +`.
- English only. Docstrings plain prose + bullet lists (no markdown/RST). No em dash. No `from __future__ import annotations`. Native 3.11+ typing (use `Self` for model_validator return).
- ANN enforced on src and tests: annotate every parameter and return `-> None`.
- Conventional Commits. Do NOT push. Do NOT create `__init__.py` under `tests/`.
- No-extra components (RegexDetector, CompositeDetector, ExactMatchDetector, ChunkedDetector, RecursiveCharacterTextSplitter) are imported at module top (matching the existing detector.py style). Extra-gated components (Gliner2/Spacy/Transformers/LLM detectors) are imported LAZILY inside build().
- After the last task: `uv run --no-sync ruff format && ruff check && pyrefly check src/piighost` clean, full suite green.

## Verified facts (rely on these)

- Current `config/models/detector.py` holds `RegexDetectorConfig` (with `patterns: dict[str,str] = Field(min_length=1)` and a `_patterns_are_compilable` field_validator), `CompositeDetectorConfig` (`detectors: "list[DetectorConfig]"`, `model_rebuild()` at end), and `DetectorConfig = Annotated[RegexDetectorConfig | CompositeDetectorConfig, Discriminator("type")]`.
- `RegexDetector(patterns)` stores `.patterns`. `ExactMatchDetector(values)` stores `.values`. `ChunkedDetector(detector, splitter=None)` stores `._detector`/`._splitter` (private).
- `piighost.components.detector` eagerly exports `RegexDetector`, `CompositeDetector`, `ExactMatchDetector`, `ChunkedDetector` (no extra); `LLMDetector` is lazy there.
- The NER detectors live in `piighost.components.detector.ner.{gliner2,spacy,transformers}`: `Gliner2Detector(model: GLiNER2 | str, labels, threshold=0.5, max_concurrency=None)`, `SpacyDetector(model: Language | str, labels=None, max_concurrency=None)`, `TransformersDetector(pipeline: ... | str, labels=None, threshold=0.0, max_concurrency=None)`. `LLMDetector(model: BaseChatModel | str, labels, prompt=None, provider=None)` is in `piighost.components.detector.llm`.
- Pattern catalogs: `piighost.components.detector.patterns` exports `EU_PATTERNS`, `FR_PATTERNS`, `GENERIC_PATTERNS`, `US_PATTERNS` (plain dicts, no extra). `GENERIC_PATTERNS` includes an `EMAIL` pattern that matches `a@b.co`.
- `piighost.text.RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100, separators=None)` (no extra), raising ValueError if chunk_overlap is not smaller than chunk_size.

---

### Task 1: Catalogs, exact, and chunked in detector.py

**Files:**
- Modify: `src/piighost/config/models/detector.py`
- Test: `tests/config/test_detectors.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/config/test_detectors.py`:

```python
"""Tests for the catalog, exact, and chunked detector config models."""

import pytest
from pydantic import TypeAdapter, ValidationError

from piighost.components.detector import (
    ChunkedDetector,
    ExactMatchDetector,
    RegexDetector,
)
from piighost.config.models.detector import (
    ChunkedDetectorConfig,
    DetectorConfig,
    ExactMatchDetectorConfig,
    RegexDetectorConfig,
)


class TestRegexCatalogs:
    def test_catalog_populates_patterns(self) -> None:
        """A catalog name fills the regex detector with the catalog's patterns."""
        detector = RegexDetectorConfig(type="regex", catalogs=["generic"]).build()
        assert isinstance(detector, RegexDetector)
        assert "EMAIL" in detector.patterns

    async def test_catalog_detector_detects(self) -> None:
        """A generic-catalog regex detector detects an email."""
        detector = RegexDetectorConfig(type="regex", catalogs=["generic"]).build()
        detections = await detector.detect("reach me at a@b.co")
        assert any(detection.label == "EMAIL" for detection in detections)

    def test_inline_overrides_catalog(self) -> None:
        """An inline pattern overrides a catalog pattern on the same label."""
        config = RegexDetectorConfig(
            type="regex", catalogs=["generic"], patterns={"EMAIL": "OVERRIDE"}
        )
        detector = config.build()
        assert detector.patterns["EMAIL"] == "OVERRIDE"

    def test_neither_patterns_nor_catalogs_is_rejected(self) -> None:
        """A regex config with no inline patterns and no catalog fails validation."""
        with pytest.raises(ValidationError):
            RegexDetectorConfig(type="regex")

    def test_unknown_catalog_name_is_rejected(self) -> None:
        """An unknown catalog name fails validation."""
        with pytest.raises(ValidationError):
            RegexDetectorConfig(type="regex", catalogs=["mars"])


class TestExactDetectorConfig:
    def test_builds_an_exact_detector(self) -> None:
        """The exact config builds an ExactMatchDetector over its values."""
        detector = ExactMatchDetectorConfig(
            type="exact", values={"Emma": "PERSON"}
        ).build()
        assert isinstance(detector, ExactMatchDetector)
        assert detector.values == {"Emma": "PERSON"}

    async def test_exact_detector_detects(self) -> None:
        """An exact detector detects a configured literal value."""
        detector = ExactMatchDetectorConfig(
            type="exact", values={"Emma": "PERSON"}
        ).build()
        detections = await detector.detect("hello Emma")
        assert any(detection.label == "PERSON" for detection in detections)


class TestChunkedDetectorConfig:
    def test_wraps_a_detector(self) -> None:
        """The chunked config builds a ChunkedDetector around its inner detector."""
        config = ChunkedDetectorConfig(
            type="chunked",
            detector={"type": "regex", "patterns": {"EMAIL": "a@b"}},
        )
        assert isinstance(config.build(), ChunkedDetector)

    def test_rejects_overlap_not_below_size(self) -> None:
        """A chunk_overlap not smaller than chunk_size fails validation."""
        with pytest.raises(ValidationError):
            ChunkedDetectorConfig(
                type="chunked",
                detector={"type": "regex", "patterns": {"A": "a"}},
                chunk_size=100,
                chunk_overlap=100,
            )


class TestDetectorUnionWidening:
    def test_union_dispatches_exact(self) -> None:
        """The exact type dispatches to ExactMatchDetectorConfig through the union."""
        adapter = TypeAdapter(DetectorConfig)
        parsed = adapter.validate_python(
            {"type": "exact", "values": {"Emma": "PERSON"}}
        )
        assert isinstance(parsed, ExactMatchDetectorConfig)

    def test_union_dispatches_chunked(self) -> None:
        """The chunked type dispatches to ChunkedDetectorConfig through the union."""
        adapter = TypeAdapter(DetectorConfig)
        parsed = adapter.validate_python(
            {"type": "chunked", "detector": {"type": "regex", "patterns": {"A": "a"}}}
        )
        assert isinstance(parsed, ChunkedDetectorConfig)

    def test_guard_config_accepts_a_nested_exact_detector(self) -> None:
        """A guard detector config accepts the newly widened exact detector type."""
        from piighost.config.models.guard import GuardConfig

        adapter = TypeAdapter(GuardConfig)
        parsed = adapter.validate_python(
            {
                "type": "detector",
                "detector": {"type": "exact", "values": {"Emma": "PERSON"}},
            }
        )
        assert isinstance(parsed.detector, ExactMatchDetectorConfig)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/config/test_detectors.py -q`
Expected: FAIL with `ImportError: cannot import name 'ChunkedDetectorConfig'`.

- [ ] **Step 3: Rewrite detector.py**

Replace the entire contents of `src/piighost/config/models/detector.py` with:

```python
"""Detector configuration models, discriminated on type."""

import re
from typing import Annotated, Literal, Self

from pydantic import Discriminator, Field, field_validator, model_validator

from piighost.components.detector import (
    ChunkedDetector,
    CompositeDetector,
    ExactMatchDetector,
    RegexDetector,
)
from piighost.components.detector.base import AnyDetector
from piighost.components.detector.patterns import (
    EU_PATTERNS,
    FR_PATTERNS,
    GENERIC_PATTERNS,
    US_PATTERNS,
)
from piighost.config.models.common import _ComponentConfig
from piighost.text import RecursiveCharacterTextSplitter

CatalogName = Literal["generic", "us", "eu", "fr"]

_CATALOGS: dict[str, dict[str, str]] = {
    "generic": GENERIC_PATTERNS,
    "us": US_PATTERNS,
    "eu": EU_PATTERNS,
    "fr": FR_PATTERNS,
}
"""The prebuilt pattern catalogs a regex detector config can pull by name."""


class RegexDetectorConfig(_ComponentConfig):
    """Config for the regex detector, patterns from inline entries and catalogs.

    The final pattern set merges the named catalogs first, then the inline
    patterns, so an inline pattern overrides a catalog pattern on the same label.

    Attributes:
        patterns: Inline label to regex mappings, optional when a catalog is set.
        catalogs: Names of prebuilt catalogs to pull, among generic, us, eu, fr.
    """

    type: Literal["regex"]
    patterns: dict[str, str] = Field(default_factory=dict)
    catalogs: list[CatalogName] = Field(default_factory=list)

    @field_validator("patterns")
    @classmethod
    def _patterns_are_compilable(cls, patterns: dict[str, str]) -> dict[str, str]:
        """Reject a pattern that is not a compilable regex at load time.

        Without this a malformed pattern parses fine and only raises a raw
        re.error later, when the detector first runs; validating here turns it
        into a configuration error the caller sees at load time.
        """
        for label, pattern in patterns.items():
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(
                    f"pattern for label {label} is not a valid regex: {exc}"
                ) from exc
        return patterns

    @model_validator(mode="after")
    def _has_some_patterns(self) -> Self:
        """Require at least one inline pattern or one catalog."""
        if not self.patterns and not self.catalogs:
            raise ValueError("a regex detector needs inline patterns or a catalog")
        return self

    def build(self) -> AnyDetector:
        """Build a RegexDetector over the merged catalog and inline patterns."""
        merged: dict[str, str] = {}
        for name in self.catalogs:
            merged.update(_CATALOGS[name])
        merged.update(self.patterns)
        return RegexDetector(merged)


class CompositeDetectorConfig(_ComponentConfig):
    """Config for the composite detector, running child detectors together."""

    type: Literal["composite"]
    detectors: "list[DetectorConfig]" = Field(min_length=1)

    def build(self) -> AnyDetector:
        """Build a CompositeDetector from the built child detectors."""
        children = [detector.build() for detector in self.detectors]
        return CompositeDetector(children)


class ExactMatchDetectorConfig(_ComponentConfig):
    """Config for the exact-match detector, literal values mapped to labels."""

    type: Literal["exact"]
    values: dict[str, str] = Field(min_length=1)

    def build(self) -> AnyDetector:
        """Build an ExactMatchDetector over the configured values."""
        return ExactMatchDetector(self.values)


class ChunkedDetectorConfig(_ComponentConfig):
    """Config for the chunked detector, wrapping a detector with a splitter.

    Attributes:
        detector: The detector run on each chunk.
        chunk_size: The maximum size of a chunk the splitter emits.
        chunk_overlap: The overlap kept between consecutive chunks.
    """

    type: Literal["chunked"]
    detector: "DetectorConfig"
    chunk_size: int = Field(default=1000, gt=0)
    chunk_overlap: int = Field(default=100, ge=0)

    @model_validator(mode="after")
    def _overlap_below_size(self) -> Self:
        """Require the overlap to stay below the chunk size."""
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self

    def build(self) -> AnyDetector:
        """Build a ChunkedDetector wrapping the built inner detector."""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap
        )
        detector = self.detector.build()
        return ChunkedDetector(detector, splitter=splitter)


DetectorConfig = Annotated[
    RegexDetectorConfig
    | CompositeDetectorConfig
    | ExactMatchDetectorConfig
    | ChunkedDetectorConfig,
    Discriminator("type"),
]


CompositeDetectorConfig.model_rebuild()
ChunkedDetectorConfig.model_rebuild()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/config/test_detectors.py tests/config/test_models.py tests/config/test_settings.py -q`
Expected: PASS (the new tests plus the pre-existing regex/composite tests still green).

- [ ] **Step 5: Lint, types, commit**

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: clean, 0 errors.

```bash
git add src/piighost/config/models/detector.py tests/config/test_detectors.py
git commit -m "feat(config): add catalog, exact, and chunked detector configs"
```

---

### Task 2: The four model-backed detector configs

**Files:**
- Create: `src/piighost/config/models/detector_model.py`
- Modify: `src/piighost/config/models/detector.py` (extend the union)
- Test: `tests/config/test_model_detectors.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/config/test_model_detectors.py`:

```python
"""Tests for the model-backed detector config models (parse and dispatch only).

The gliner2, spacy, and transformers extras and an llm provider package are
absent from the dev environment, so these configs are exercised at the parse and
union-dispatch level; their build() is a deployment concern covered by the
components' own tests.
"""

import pytest
from pydantic import TypeAdapter

from piighost.config.models.detector import DetectorConfig
from piighost.config.models.detector_model import (
    Gliner2DetectorConfig,
    LLMDetectorConfig,
    SpacyDetectorConfig,
    TransformersDetectorConfig,
)


class TestModelDetectorParsing:
    def test_gliner2_parses_and_stores_fields(self) -> None:
        """The gliner2 config parses model, labels, and threshold."""
        config = Gliner2DetectorConfig(
            type="gliner2",
            model="urchade/gliner_small",
            labels=["PERSON"],
            threshold=0.7,
        )
        assert config.model == "urchade/gliner_small"
        assert config.labels == ["PERSON"]
        assert config.threshold == 0.7

    def test_spacy_parses_with_dict_labels(self) -> None:
        """The spacy config parses an emitted-to-model label mapping."""
        config = SpacyDetectorConfig(
            type="spacy", model="en_core_web_sm", labels={"PER": "PERSON"}
        )
        assert config.labels == {"PER": "PERSON"}

    def test_transformers_parses_threshold(self) -> None:
        """The transformers config parses the model and score threshold."""
        config = TransformersDetectorConfig(
            type="transformers", model="dslim/bert-base-NER", threshold=0.9
        )
        assert config.model == "dslim/bert-base-NER"
        assert config.threshold == 0.9

    def test_llm_parses_prompt_and_provider(self) -> None:
        """The llm config parses model, labels, prompt, and provider."""
        config = LLMDetectorConfig(
            type="llm",
            model="openai:gpt-4o-mini",
            labels=["PERSON"],
            provider="openai",
        )
        assert config.provider == "openai"


_DISPATCH_CASES = [
    ({"type": "gliner2", "model": "m", "labels": ["A"]}, Gliner2DetectorConfig),
    ({"type": "spacy", "model": "m"}, SpacyDetectorConfig),
    ({"type": "transformers", "model": "m"}, TransformersDetectorConfig),
    ({"type": "llm", "model": "m", "labels": ["A"]}, LLMDetectorConfig),
]


@pytest.mark.parametrize(("data", "expected"), _DISPATCH_CASES)
def test_model_type_dispatches(data: dict[str, object], expected: type) -> None:
    """Each model detector type dispatches to its config through the union."""
    adapter = TypeAdapter(DetectorConfig)
    assert isinstance(adapter.validate_python(data), expected)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/config/test_model_detectors.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'piighost.config.models.detector_model'`.

- [ ] **Step 3: Create detector_model.py**

Create `src/piighost/config/models/detector_model.py`:

```python
"""Model-backed detector configuration models, discriminated on type.

Each config needs an optional extra, so build() imports the concrete detector
lazily and a missing extra surfaces as the component's own ImportError naming
the extra to install. The port AnyDetector is imported at module top only for
the build() return annotation.
"""

from typing import Literal

from pydantic import Field

from piighost.components.detector.base import AnyDetector
from piighost.config.models.common import _ComponentConfig


class Gliner2DetectorConfig(_ComponentConfig):
    """Config for the GLiNER2 detector, a zero-shot NER model."""

    type: Literal["gliner2"]
    model: str
    labels: list[str] | dict[str, str]
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    max_concurrency: int | None = Field(default=None, ge=1)

    def build(self) -> AnyDetector:
        """Build a Gliner2Detector loading the named model."""
        from piighost.components.detector.ner.gliner2 import Gliner2Detector

        return Gliner2Detector(
            model=self.model,
            labels=self.labels,
            threshold=self.threshold,
            max_concurrency=self.max_concurrency,
        )


class SpacyDetectorConfig(_ComponentConfig):
    """Config for the spaCy detector, a pipeline NER model."""

    type: Literal["spacy"]
    model: str
    labels: list[str] | dict[str, str] | None = None
    max_concurrency: int | None = Field(default=None, ge=1)

    def build(self) -> AnyDetector:
        """Build a SpacyDetector loading the named pipeline."""
        from piighost.components.detector.ner.spacy import SpacyDetector

        return SpacyDetector(
            model=self.model,
            labels=self.labels,
            max_concurrency=self.max_concurrency,
        )


class TransformersDetectorConfig(_ComponentConfig):
    """Config for the Transformers detector, a token-classification pipeline."""

    type: Literal["transformers"]
    model: str
    labels: list[str] | dict[str, str] | None = None
    threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    max_concurrency: int | None = Field(default=None, ge=1)

    def build(self) -> AnyDetector:
        """Build a TransformersDetector from the named model.

        The model field is passed to the detector's pipeline parameter, which
        accepts a model name and builds the token-classification pipeline.
        """
        from piighost.components.detector.ner.transformers import TransformersDetector

        return TransformersDetector(
            pipeline=self.model,
            labels=self.labels,
            threshold=self.threshold,
            max_concurrency=self.max_concurrency,
        )


class LLMDetectorConfig(_ComponentConfig):
    """Config for the LLM detector, extracting entities via a chat model."""

    type: Literal["llm"]
    model: str
    labels: list[str] | dict[str, str]
    prompt: str | None = None
    provider: str | None = None

    def build(self) -> AnyDetector:
        """Build an LLMDetector from the model, labels, prompt, and provider."""
        from piighost.components.detector.llm import LLMDetector

        return LLMDetector(
            model=self.model,
            labels=self.labels,
            prompt=self.prompt,
            provider=self.provider,
        )
```

- [ ] **Step 4: Extend the union in detector.py**

In `src/piighost/config/models/detector.py`, add this import after the existing `from piighost.text import RecursiveCharacterTextSplitter` line:

```python
from piighost.config.models.detector_model import (
    Gliner2DetectorConfig,
    LLMDetectorConfig,
    SpacyDetectorConfig,
    TransformersDetectorConfig,
)
```

Replace the `DetectorConfig` union definition (the `Annotated[...]` block) with:

```python
DetectorConfig = Annotated[
    RegexDetectorConfig
    | CompositeDetectorConfig
    | ExactMatchDetectorConfig
    | ChunkedDetectorConfig
    | Gliner2DetectorConfig
    | SpacyDetectorConfig
    | TransformersDetectorConfig
    | LLMDetectorConfig,
    Discriminator("type"),
]
```

Leave the two `model_rebuild()` calls at the end unchanged.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/config/ -q`
Expected: PASS.

- [ ] **Step 6: Full suite, lint, types**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest -q`
Expected: full suite PASS.

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: clean, 0 errors.

- [ ] **Step 7: Commit**

```bash
git add src/piighost/config/models/detector_model.py src/piighost/config/models/detector.py tests/config/test_model_detectors.py
git commit -m "feat(config): add the model-backed detector configs"
```

---

## Notes for the implementer

- `model` is always a `str` in config (a model name or path). The `model | str` object branch of the core detectors is not exposed, since a TOML cannot carry a live model object. This is the documented limitation.
- Do NOT call `build()` on gliner2/spacy/transformers/llm configs in tests: the extras and provider packages are absent in dev, and building would import them. Parse and dispatch only.
- Widening is automatic: `guard.detector`, `override.whitelist`/`blacklist`, `composite.detectors`, and `chunked.detector` all type as `DetectorConfig`, so they accept the new detector types without any change to their modules.
- Keep the one-way coupling: config imports core, never the reverse. No new exception, nothing added to `PUBLIC_API`.
- `RecursiveCharacterTextSplitter` and `ChunkedDetector`/`ExactMatchDetector` carry no extra, so they are imported eagerly at the top of detector.py, matching the existing `RegexDetector`/`CompositeDetector` imports there.
