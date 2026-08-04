# Config Coverage A: Optional Stages and Hash Factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the AnonymizationPipeline's six optional stages (overlap_resolver, expander, entity_resolver, guard, override, observation_redactor) and the label_hash factory in the TOML config, each config model carrying a build().

**Architecture:** Five new `config/models/` modules plus a `label_hash` addition to `placeholder.py`, each model with a `build()` that lazily imports and constructs its core component (extras stay optional). `PipelineConfig` gains six optional fields and an extended `build()`. Single-adapter stages are plain aliases (like `LinkerConfig`); multi-adapter stages are `Discriminator("type")` unions.

**Tech Stack:** Python 3.11+, pydantic + pydantic-settings, the existing core components. Dev env has rapidfuzz, langchain, mistralai.client, opentelemetry.

---

## Conventions for every task

- Run with `uv run --no-sync`. Before each pytest run: `find src tests -name __pycache__ -type d -exec rm -rf {} +`.
- English only. Docstrings plain prose + bullet lists (no markdown/RST). No em dash. No `from __future__ import annotations`. Native 3.11+ typing. Conventional Commits. Do NOT push. Do NOT create `__init__.py` under `tests/`.
- ANN enforced on src and tests: annotate every parameter and return `-> None`.
- Ports (`Any*`) and override strategy enums are imported at module top for annotations and field types; concrete component classes are imported lazily inside `build()` so a missing extra fails only when that stage is actually built.
- After the last task, verify: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost` clean, and the full suite green.

## File structure

- Create `src/piighost/config/models/overlap_resolver.py` — ConfidenceOverlapResolverConfig + OverlapResolverConfig alias.
- Create `src/piighost/config/models/expander.py` — WordBoundaryExpanderConfig + ExpanderConfig alias.
- Create `src/piighost/config/models/entity_resolver.py` — merge/separate/fuzzy configs + EntityResolverConfig union.
- Create `src/piighost/config/models/guard.py` — detector/llm/moderation configs + GuardConfig union.
- Create `src/piighost/config/models/override.py` — OverrideConfig.
- Modify `src/piighost/config/models/placeholder.py` — add LabelHashPlaceholderConfig to the union.
- Modify `src/piighost/config/settings.py` — six optional fields on PipelineConfig + extended build().
- Create `tests/config/test_stage_models.py` (Task 1), `tests/config/test_guard_override_models.py` (Task 2). Extend `tests/config/test_settings.py` (Task 3).

## Verified facts (rely on these)

- Component ctors: `ConfidenceOverlapResolver()` (no args); `WordBoundaryExpander(case_sensitive=False)`; `MergeEntityResolver()`, `SeparateEntityResolver()`, `FuzzyEntityResolver(threshold=0.85)`; `DetectorGuardRail(detector)`; `LLMGuardRail(model, labels, prompt=None, provider=None)`; `ModerationGuardRail(client, model="mistral-moderation-latest", threshold=0.5)`; `DetectionOverride(whitelist=None, blacklist=None, blacklist_strategy=EXACT, whitelist_strategy=RESPECT_PROVENANCE, conflict_strategy=WHITELIST_WINS)`; `LabelHashPlaceholderFactory(hash_length=8)`.
- Exports: `piighost.components.overlap_resolver.base.AnyOverlapResolver`; `.expander.base.AnyDetectionExpander`; `.entity_resolver.base.AnyEntityResolver`; `.guard.base.AnyGuardRail`; `.override.base.AnyDetectionOverride`; `.override.strategy.{BlacklistStrategy,WhitelistStrategy,OverrideConflictStrategy}`. Concrete classes live in the named submodules (`.confidence`, `.word_boundary`, `.merge`, `.separate`, `.fuzzy`, `.detector`, `.llm`, `.moderation`, and `DetectionOverride` in `override/detector.py`).
- The strategy enum values are: BlacklistStrategy `exact`/`value`/`overlap`; WhitelistStrategy `respect_provenance`/`force`; OverrideConflictStrategy `whitelist_wins`/`blacklist_wins`/`raise`.
- Regex detections all carry confidence 1.0, so overlap-by-confidence cannot be shown end to end with regex; test the overlap/expander/entity_resolver wiring by type, not by effect.
- The pipeline raises `PIIRemainingError` (from `piighost.exceptions`) when a guard flags residual PII.
- `AnonymizationPipeline.__init__(detector, linker, anonymizer, overlap_resolver=None, expander=None, entity_resolver=None, guard=None, observation_redactor=None, override=None)`.
- `LLMGuardRail(model="...")` calls `init_chat_model` at construction (needs a provider package + credentials), so its build() is NOT exercised in tests. `ModerationGuardRail` build() works with a dummy `MISTRAL_API_KEY` (mistralai.client is present in dev).

---

### Task 1: Simple stage models and the hash factory

**Files:**
- Create: `src/piighost/config/models/overlap_resolver.py`
- Create: `src/piighost/config/models/expander.py`
- Create: `src/piighost/config/models/entity_resolver.py`
- Modify: `src/piighost/config/models/placeholder.py`
- Test: `tests/config/test_stage_models.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/config/test_stage_models.py`:

```python
"""Tests for the optional-stage config models and the hash factory."""

from pydantic import TypeAdapter

from piighost.components.entity_resolver import (
    FuzzyEntityResolver,
    MergeEntityResolver,
    SeparateEntityResolver,
)
from piighost.components.expander import WordBoundaryExpander
from piighost.components.overlap_resolver import ConfidenceOverlapResolver
from piighost.components.placeholder import LabelHashPlaceholderFactory
from piighost.config.models.entity_resolver import (
    EntityResolverConfig,
    FuzzyEntityResolverConfig,
    MergeEntityResolverConfig,
    SeparateEntityResolverConfig,
)
from piighost.config.models.expander import WordBoundaryExpanderConfig
from piighost.config.models.overlap_resolver import ConfidenceOverlapResolverConfig
from piighost.config.models.placeholder import LabelHashPlaceholderConfig
from piighost.models import Detection, Entity, Span


def _entity(text: str = "Emma", label: str = "PERSON") -> Entity:
    """Build a one-detection entity for a value and label."""
    detection = Detection(span=Span(0, len(text)), text=text, label=label, confidence=1.0)
    return Entity((detection,))


class TestOverlapResolverConfig:
    def test_builds_a_confidence_resolver(self) -> None:
        """The confidence config builds a ConfidenceOverlapResolver."""
        resolver = ConfidenceOverlapResolverConfig(type="confidence").build()
        assert isinstance(resolver, ConfidenceOverlapResolver)


class TestExpanderConfig:
    def test_builds_a_word_boundary_expander(self) -> None:
        """The word_boundary config builds a WordBoundaryExpander."""
        expander = WordBoundaryExpanderConfig(type="word_boundary").build()
        assert isinstance(expander, WordBoundaryExpander)

    def test_forwards_case_sensitive(self) -> None:
        """The config forwards case_sensitive to the expander."""
        expander = WordBoundaryExpanderConfig(
            type="word_boundary", case_sensitive=True
        ).build()
        assert expander.case_sensitive is True


class TestEntityResolverConfig:
    def test_merge_builds(self) -> None:
        """The merge config builds a MergeEntityResolver."""
        assert isinstance(MergeEntityResolverConfig(type="merge").build(), MergeEntityResolver)

    def test_separate_builds(self) -> None:
        """The separate config builds a SeparateEntityResolver."""
        resolver = SeparateEntityResolverConfig(type="separate").build()
        assert isinstance(resolver, SeparateEntityResolver)

    def test_fuzzy_builds_and_forwards_threshold(self) -> None:
        """The fuzzy config builds a FuzzyEntityResolver over its threshold."""
        resolver = FuzzyEntityResolverConfig(type="fuzzy", threshold=0.7).build()
        assert isinstance(resolver, FuzzyEntityResolver)
        assert resolver.threshold == 0.7

    def test_union_dispatches_on_type(self) -> None:
        """The type discriminant selects the matching resolver config."""
        adapter = TypeAdapter(EntityResolverConfig)
        parsed = adapter.validate_python({"type": "fuzzy", "threshold": 0.9})
        assert isinstance(parsed, FuzzyEntityResolverConfig)


class TestLabelHashPlaceholderConfig:
    def test_builds_and_renders_a_hashed_token(self) -> None:
        """The label_hash config builds a factory rendering a hashed token."""
        factory = LabelHashPlaceholderConfig(type="label_hash", hash_length=8).build()
        assert isinstance(factory, LabelHashPlaceholderFactory)
        entities = [_entity()]
        token = factory.create(entities)[entities[0]]
        assert token.startswith("<<PERSON:") and token.endswith(">>")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/config/test_stage_models.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'piighost.config.models.overlap_resolver'`.

- [ ] **Step 3: Write the three stage modules**

Create `src/piighost/config/models/overlap_resolver.py`:

```python
"""Overlap resolver configuration model."""

from typing import Literal

from piighost.components.overlap_resolver.base import AnyOverlapResolver
from piighost.config.models.common import _ComponentConfig


class ConfidenceOverlapResolverConfig(_ComponentConfig):
    """Config for the confidence overlap resolver, keeping the surest span."""

    type: Literal["confidence"]

    def build(self) -> AnyOverlapResolver:
        """Build a ConfidenceOverlapResolver."""
        from piighost.components.overlap_resolver.confidence import (
            ConfidenceOverlapResolver,
        )

        return ConfidenceOverlapResolver()


OverlapResolverConfig = ConfidenceOverlapResolverConfig
"""The overlap resolver configuration.

A plain alias while one resolver exists; it becomes a discriminated union when a
second resolver lands.
"""
```

Create `src/piighost/config/models/expander.py`:

```python
"""Detection expander configuration model."""

from typing import Literal

from piighost.components.expander.base import AnyDetectionExpander
from piighost.config.models.common import _ComponentConfig


class WordBoundaryExpanderConfig(_ComponentConfig):
    """Config for the word-boundary expander, adding missed whole-word hits."""

    type: Literal["word_boundary"]
    case_sensitive: bool = False

    def build(self) -> AnyDetectionExpander:
        """Build a WordBoundaryExpander with the configured case sensitivity."""
        from piighost.components.expander.word_boundary import WordBoundaryExpander

        return WordBoundaryExpander(case_sensitive=self.case_sensitive)


ExpanderConfig = WordBoundaryExpanderConfig
"""The expander configuration.

A plain alias while one expander exists; it becomes a discriminated union when a
second expander lands.
"""
```

Create `src/piighost/config/models/entity_resolver.py`:

```python
"""Entity resolver configuration models, discriminated on type."""

from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.components.entity_resolver.base import AnyEntityResolver
from piighost.config.models.common import _ComponentConfig

_DEFAULT_FUZZY_THRESHOLD = 0.85
"""Default Jaro-Winkler similarity above which two entities are clustered."""


class MergeEntityResolverConfig(_ComponentConfig):
    """Config for the merge resolver, unioning entities that share detections."""

    type: Literal["merge"]

    def build(self) -> AnyEntityResolver:
        """Build a MergeEntityResolver."""
        from piighost.components.entity_resolver.merge import MergeEntityResolver

        return MergeEntityResolver()


class SeparateEntityResolverConfig(_ComponentConfig):
    """Config for the separate resolver, keeping every entity distinct."""

    type: Literal["separate"]

    def build(self) -> AnyEntityResolver:
        """Build a SeparateEntityResolver."""
        from piighost.components.entity_resolver.separate import SeparateEntityResolver

        return SeparateEntityResolver()


class FuzzyEntityResolverConfig(_ComponentConfig):
    """Config for the fuzzy resolver, clustering near-duplicate entities."""

    type: Literal["fuzzy"]
    threshold: float = Field(default=_DEFAULT_FUZZY_THRESHOLD, ge=0.0, le=1.0)

    def build(self) -> AnyEntityResolver:
        """Build a FuzzyEntityResolver over the configured threshold."""
        from piighost.components.entity_resolver.fuzzy import FuzzyEntityResolver

        return FuzzyEntityResolver(threshold=self.threshold)


EntityResolverConfig = Annotated[
    MergeEntityResolverConfig
    | SeparateEntityResolverConfig
    | FuzzyEntityResolverConfig,
    Discriminator("type"),
]
```

Modify `src/piighost/config/models/placeholder.py`: add `LabelHashPlaceholderFactory` to the existing factory import, add the config class after `MaskPlaceholderConfig`, and add the member to the union.

Add to the import block (alongside the other factories):

```python
from piighost.components.placeholder import (
    LabelCounterPlaceholderFactory,
    LabelHashPlaceholderFactory,
    LabelPlaceholderFactory,
    MaskPlaceholderFactory,
    RedactPlaceholderFactory,
)
```

Add the `Field` import if not present (it is used by MaskPlaceholderConfig already, so `Field` is imported). Add this class after `MaskPlaceholderConfig`:

```python
class LabelHashPlaceholderConfig(_ComponentConfig):
    """Config for the label-hash factory, a hashed token per label."""

    type: Literal["label_hash"]
    hash_length: int = Field(default=8, ge=1)

    def build(self) -> AnyPlaceholderFactory[PlaceholderPreservation]:
        """Build the label-hash placeholder factory with the digest length."""
        return LabelHashPlaceholderFactory(hash_length=self.hash_length)
```

Extend the union to include it:

```python
PlaceholderConfig = Annotated[
    RedactPlaceholderConfig
    | LabelPlaceholderConfig
    | LabelCounterPlaceholderConfig
    | MaskPlaceholderConfig
    | LabelHashPlaceholderConfig,
    Discriminator("type"),
]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/config/test_stage_models.py tests/config/test_models.py -q`
Expected: PASS.

- [ ] **Step 5: Lint, types, commit**

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: clean, 0 errors.

```bash
git add src/piighost/config/models/overlap_resolver.py src/piighost/config/models/expander.py src/piighost/config/models/entity_resolver.py src/piighost/config/models/placeholder.py tests/config/test_stage_models.py
git commit -m "feat(config): add stage and hash-factory config models"
```

---

### Task 2: Guard and override models

**Files:**
- Create: `src/piighost/config/models/guard.py`
- Create: `src/piighost/config/models/override.py`
- Test: `tests/config/test_guard_override_models.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/config/test_guard_override_models.py`:

```python
"""Tests for the guard and override config models."""

import pytest
from pydantic import TypeAdapter

from piighost.components.detector import RegexDetector
from piighost.components.guard import (
    DetectorGuardRail,
    ModerationGuardRail,
)
from piighost.components.override import (
    BlacklistStrategy,
    DetectionOverride,
    OverrideConflictStrategy,
    WhitelistStrategy,
)
from piighost.config.models.guard import (
    DetectorGuardRailConfig,
    GuardConfig,
    LLMGuardRailConfig,
    ModerationGuardRailConfig,
)
from piighost.config.models.override import OverrideConfig

_REGEX = {"type": "regex", "patterns": {"EMAIL": "[a-z]+@[a-z.]+"}}


class TestGuardConfig:
    def test_detector_guard_builds_over_its_detector(self) -> None:
        """The detector guard config builds a DetectorGuardRail on its detector."""
        config = DetectorGuardRailConfig(type="detector", detector=_REGEX)
        guard = config.build()
        assert isinstance(guard, DetectorGuardRail)
        assert isinstance(guard.detector, RegexDetector)

    def test_moderation_guard_builds_with_env_credentials(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The moderation guard config builds a ModerationGuardRail from the env."""
        monkeypatch.setenv("MISTRAL_API_KEY", "test")
        config = ModerationGuardRailConfig(type="moderation", threshold=0.3)
        guard = config.build()
        assert isinstance(guard, ModerationGuardRail)
        assert guard.threshold == 0.3

    def test_llm_guard_parses_and_dispatches(self) -> None:
        """The llm type dispatches to LLMGuardRailConfig without building it."""
        adapter = TypeAdapter(GuardConfig)
        parsed = adapter.validate_python(
            {"type": "llm", "model": "openai:gpt-4o-mini", "labels": ["PERSON"]}
        )
        assert isinstance(parsed, LLMGuardRailConfig)
        assert parsed.model == "openai:gpt-4o-mini"

    def test_union_dispatches_detector(self) -> None:
        """The detector type dispatches to DetectorGuardRailConfig."""
        adapter = TypeAdapter(GuardConfig)
        parsed = adapter.validate_python({"type": "detector", "detector": _REGEX})
        assert isinstance(parsed, DetectorGuardRailConfig)


class TestOverrideConfig:
    def test_builds_a_detection_override(self) -> None:
        """The override config builds a DetectionOverride with default strategies."""
        config = OverrideConfig(blacklist=_REGEX)
        override = config.build()
        assert isinstance(override, DetectionOverride)
        assert isinstance(override.blacklist, RegexDetector)
        assert override.whitelist is None
        assert override.blacklist_strategy is BlacklistStrategy.EXACT
        assert override.whitelist_strategy is WhitelistStrategy.RESPECT_PROVENANCE
        assert override.conflict_strategy is OverrideConflictStrategy.WHITELIST_WINS

    def test_parses_strategies_from_strings(self) -> None:
        """The strategy fields parse from their TOML string values."""
        config = OverrideConfig(
            whitelist=_REGEX,
            blacklist_strategy="value",
            whitelist_strategy="force",
            conflict_strategy="blacklist_wins",
        )
        assert config.blacklist_strategy is BlacklistStrategy.VALUE
        assert config.whitelist_strategy is WhitelistStrategy.FORCE
        assert config.conflict_strategy is OverrideConflictStrategy.BLACKLIST_WINS
```

- [ ] **Step 2: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/config/test_guard_override_models.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'piighost.config.models.guard'`.

- [ ] **Step 3: Write the guard and override modules**

Create `src/piighost/config/models/guard.py`:

```python
"""Guard rail configuration models, discriminated on type."""

import os
from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.components.guard.base import AnyGuardRail
from piighost.config.models.common import _ComponentConfig
from piighost.config.models.detector import DetectorConfig

_DEFAULT_MODERATION_MODEL = "mistral-moderation-latest"
"""The Mistral moderation model the moderation guard scores with by default."""

_DEFAULT_MODERATION_THRESHOLD = 0.5
"""The category score above which the moderation guard flags the text."""


class DetectorGuardRailConfig(_ComponentConfig):
    """Config for the detector guard, re-running a detector on the output."""

    type: Literal["detector"]
    detector: DetectorConfig

    def build(self) -> AnyGuardRail:
        """Build a DetectorGuardRail over the built detector."""
        from piighost.components.guard.detector import DetectorGuardRail

        detector = self.detector.build()
        return DetectorGuardRail(detector)


class LLMGuardRailConfig(_ComponentConfig):
    """Config for the LLM guard, prompting a model to find residual PII."""

    type: Literal["llm"]
    model: str
    labels: list[str] | dict[str, str]
    prompt: str | None = None
    provider: str | None = None

    def build(self) -> AnyGuardRail:
        """Build an LLMGuardRail from the model, labels, prompt, and provider."""
        from piighost.components.guard.llm import LLMGuardRail

        return LLMGuardRail(
            model=self.model,
            labels=self.labels,
            prompt=self.prompt,
            provider=self.provider,
        )


class ModerationGuardRailConfig(_ComponentConfig):
    """Config for the moderation guard, scoring the output with Mistral."""

    type: Literal["moderation"]
    model: str = _DEFAULT_MODERATION_MODEL
    threshold: float = Field(default=_DEFAULT_MODERATION_THRESHOLD, ge=0.0, le=1.0)

    def build(self) -> AnyGuardRail:
        """Build a ModerationGuardRail over a Mistral client read from the env."""
        from mistralai.client import Mistral

        from piighost.components.guard.moderation import ModerationGuardRail

        api_key = os.environ.get("MISTRAL_API_KEY")
        client = Mistral(api_key=api_key)
        return ModerationGuardRail(
            client=client, model=self.model, threshold=self.threshold
        )


GuardConfig = Annotated[
    DetectorGuardRailConfig | LLMGuardRailConfig | ModerationGuardRailConfig,
    Discriminator("type"),
]
```

Create `src/piighost/config/models/override.py`:

```python
"""Detection override configuration model."""

from piighost.components.override.base import AnyDetectionOverride
from piighost.components.override.strategy import (
    BlacklistStrategy,
    OverrideConflictStrategy,
    WhitelistStrategy,
)
from piighost.config.models.common import _ComponentConfig
from piighost.config.models.detector import DetectorConfig


class OverrideConfig(_ComponentConfig):
    """Config for the detection override, a whitelist and a blacklist detector.

    Attributes:
        whitelist: A detector whose hits are cleared from the set, or None.
        blacklist: A detector whose hits are forced into the set, or None.
        blacklist_strategy: How a blacklist hit matches, exact span, value, or overlap.
        whitelist_strategy: Whether a whitelist hit respects provenance or forces it.
        conflict_strategy: Which list wins when both touch the same span.
    """

    whitelist: DetectorConfig | None = None
    blacklist: DetectorConfig | None = None
    blacklist_strategy: BlacklistStrategy = BlacklistStrategy.EXACT
    whitelist_strategy: WhitelistStrategy = WhitelistStrategy.RESPECT_PROVENANCE
    conflict_strategy: OverrideConflictStrategy = OverrideConflictStrategy.WHITELIST_WINS

    def build(self) -> AnyDetectionOverride:
        """Build a DetectionOverride from the lists and the strategies."""
        from piighost.components.override.detector import DetectionOverride

        whitelist = self.whitelist.build() if self.whitelist else None
        blacklist = self.blacklist.build() if self.blacklist else None
        return DetectionOverride(
            whitelist=whitelist,
            blacklist=blacklist,
            blacklist_strategy=self.blacklist_strategy,
            whitelist_strategy=self.whitelist_strategy,
            conflict_strategy=self.conflict_strategy,
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/config/test_guard_override_models.py -q`
Expected: PASS.

- [ ] **Step 5: Lint, types, commit**

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: clean, 0 errors.

```bash
git add src/piighost/config/models/guard.py src/piighost/config/models/override.py tests/config/test_guard_override_models.py
git commit -m "feat(config): add guard and override config models"
```

---

### Task 3: Wire the optional stages into PipelineConfig

**Files:**
- Modify: `src/piighost/config/settings.py`
- Test: `tests/config/test_settings.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/config/test_settings.py` (the file already has `_write`, `_VALID_TOML`, `load_config`, `load_pipeline`, `PipelineConfig` imports). Add these imports at the top of the file:

```python
from piighost.components.entity_resolver import MergeEntityResolver
from piighost.components.expander import WordBoundaryExpander
from piighost.components.guard import DetectorGuardRail
from piighost.components.overlap_resolver import ConfidenceOverlapResolver
from piighost.components.override import DetectionOverride
from piighost.exceptions import PIIRemainingError
```

Append these test classes:

```python
_STAGES_TOML = """
[detector]
type = "regex"
patterns = { EMAIL = "[a-z]+@[a-z.]+" }

[linker]
type = "exact"

[anonymizer.placeholder]
type = "redact"

[overlap_resolver]
type = "confidence"

[expander]
type = "word_boundary"
case_sensitive = true

[entity_resolver]
type = "merge"

[override]
[override.blacklist]
type = "regex"
patterns = { CODE = "banana" }
"""


class TestOptionalStagesWiring:
    def test_pipeline_wires_every_configured_stage(self, tmp_path: Path) -> None:
        """load_pipeline wires each configured optional stage into the pipeline."""
        pipeline = load_pipeline(_write(tmp_path, _STAGES_TOML))
        assert isinstance(pipeline.overlap_resolver, ConfidenceOverlapResolver)
        assert isinstance(pipeline.expander, WordBoundaryExpander)
        assert pipeline.expander.case_sensitive is True
        assert isinstance(pipeline.entity_resolver, MergeEntityResolver)
        assert isinstance(pipeline.override, DetectionOverride)

    def test_omitted_stages_are_none(self, tmp_path: Path) -> None:
        """A config without a stage leaves that pipeline stage disabled."""
        pipeline = load_pipeline(_write(tmp_path, _VALID_TOML))
        assert pipeline.overlap_resolver is None
        assert pipeline.expander is None
        assert pipeline.entity_resolver is None
        assert pipeline.guard is None
        assert pipeline.override is None


class TestOverrideEffect:
    async def test_blacklist_forces_a_detection(self, tmp_path: Path) -> None:
        """A blacklist detector forces anonymization of a value the detector missed."""
        pipeline = load_pipeline(_write(tmp_path, _STAGES_TOML))
        result = await pipeline.anonymize("mail a@b.co about banana")
        assert "banana" not in result.text
        assert "a@b.co" not in result.text


class TestGuardEffect:
    async def test_detector_guard_raises_on_residual(self, tmp_path: Path) -> None:
        """A detector guard raises PIIRemainingError on residual clear PII."""
        toml = """
[detector]
type = "regex"
patterns = { EMAIL = "[a-z]+@[a-z.]+" }

[linker]
type = "exact"

[anonymizer.placeholder]
type = "redact"

[guard.detector]
type = "regex"
patterns = { WORD = "banana" }
"""
        pipeline = load_pipeline(_write(tmp_path, toml))
        with pytest.raises(PIIRemainingError):
            await pipeline.anonymize("mail a@b.co about banana")


class TestHashFactoryEndToEnd:
    async def test_label_hash_renders_a_hashed_token(self, tmp_path: Path) -> None:
        """A label_hash anonymizer renders a hashed token for a detection."""
        toml = _VALID_TOML.replace('type = "redact"', 'type = "label_hash"')
        pipeline = load_pipeline(_write(tmp_path, toml))
        result = await pipeline.anonymize("mail a@b.co now")
        assert re.search(r"<<EMAIL:[0-9a-f]{8}>>", result.text)


class TestObservationRedactorWiring:
    def test_observation_redactor_is_wired(self, tmp_path: Path) -> None:
        """An observation_redactor placeholder config wires into the pipeline."""
        toml = _VALID_TOML + '\n[observation_redactor]\ntype = "label"\n'
        pipeline = load_pipeline(_write(tmp_path, toml))
        assert pipeline.observation_redactor is not None
```

Add `import re` to the top of the file if not already present.

- [ ] **Step 2: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/config/test_settings.py -q`
Expected: FAIL (the new fields do not exist on PipelineConfig, so `pipeline.overlap_resolver` is unset or the config rejects the `[overlap_resolver]` table under `extra="forbid"`).

- [ ] **Step 3: Add the fields and extend build()**

In `src/piighost/config/settings.py`, add these imports next to the existing config-model imports (`AnonymizerConfig`, `DetectorConfig`, `LinkerConfig`):

```python
from piighost.config.models.entity_resolver import EntityResolverConfig
from piighost.config.models.expander import ExpanderConfig
from piighost.config.models.guard import GuardConfig
from piighost.config.models.overlap_resolver import OverlapResolverConfig
from piighost.config.models.override import OverrideConfig
from piighost.config.models.placeholder import PlaceholderConfig
```

Add the six optional fields to `PipelineConfig`, after the `anonymizer` field:

```python
    overlap_resolver: OverlapResolverConfig | None = None
    expander: ExpanderConfig | None = None
    entity_resolver: EntityResolverConfig | None = None
    guard: GuardConfig | None = None
    override: OverrideConfig | None = None
    observation_redactor: PlaceholderConfig | None = None
```

Replace the `build()` method body with:

```python
    def build(self) -> AnonymizationPipeline[PlaceholderPreservation]:
        """Assemble the AnonymizationPipeline the configuration describes."""
        detector = self.detector.build()
        linker = self.linker.build()
        anonymizer = self.anonymizer.build()
        overlap_resolver = (
            self.overlap_resolver.build() if self.overlap_resolver else None
        )
        expander = self.expander.build() if self.expander else None
        entity_resolver = (
            self.entity_resolver.build() if self.entity_resolver else None
        )
        guard = self.guard.build() if self.guard else None
        override = self.override.build() if self.override else None
        observation_redactor = (
            self.observation_redactor.build() if self.observation_redactor else None
        )
        return AnonymizationPipeline(
            detector,
            linker,
            anonymizer,
            overlap_resolver=overlap_resolver,
            expander=expander,
            entity_resolver=entity_resolver,
            guard=guard,
            observation_redactor=observation_redactor,
            override=override,
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/config/ -q`
Expected: PASS.

- [ ] **Step 5: Full suite, lint, types**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest -q`
Expected: full suite PASS.

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: clean, 0 errors.

- [ ] **Step 6: Commit**

```bash
git add src/piighost/config/settings.py tests/config/test_settings.py
git commit -m "feat(config): wire the optional pipeline stages into PipelineConfig"
```

---

## Notes for the implementer

- Import ports (`Any*`) and the override strategy enums at module top (for annotations and field types); import concrete component classes lazily inside `build()` so a missing extra (fuzzy, llm, mistral) fails only when that stage is built, never at config import.
- The guard `detector` and the override `whitelist`/`blacklist` nest a `DetectorConfig`, which is still limited to `regex` and `composite` until sub-lot B widens it. That is expected.
- Do not exercise the llm guard `build()` in tests: `LLMGuardRail` calls `init_chat_model` at construction, needing a provider package and credentials. Test the llm config only at parse/dispatch level.
- Nothing is added to `PUBLIC_API`: no new exception, and the config models are behind the config extra, covered by the module-walk regression.
- Keep the one-way coupling: config imports core, never the reverse.
