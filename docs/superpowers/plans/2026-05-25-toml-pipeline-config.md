# TOML pipeline configuration implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `piighost.config` sub-package that loads a declarative TOML file into a working `ThreadAnonymizationPipeline`, plus a `piighost` CLI exposing `validate` and `schema`.

**Architecture:** Pydantic v2 discriminated unions describe each component (`type`-discriminated). Each existing component class gains a `Config: ClassVar` and a `from_config()` classmethod. Small `dict[type[Config], type[Component]]` mappings drive the factory dispatch. JSON Schema export feeds the future configuration UI.

**Tech Stack:** Python 3.10+, Pydantic v2, `tomllib` (3.11+) / `tomli` (3.10 backport), Typer (CLI), pytest + pytest-asyncio.

**Scope:** This plan covers the `piighost` library only. The `piighost-api` migration (CLI signature change, `/v1/labels` route, removal of `loader.py`) will be planned and executed in its own repository once this lands.

**Reference spec:** `docs/superpowers/specs/2026-05-25-toml-pipeline-config-design.md`

---

## File structure

```
src/piighost/config/                    NEW sub-package
├── __init__.py                         # public API
├── loader.py                           # load_config + build_pipeline + load_pipeline + export_schema
├── builders.py                         # type[Config] -> type[Component] mappings
├── errors.py                           # ConfigError + from_pydantic translator
└── models/
    ├── __init__.py
    ├── common.py                       # _ComponentConfig base
    ├── detector.py                     # discriminated union
    ├── span_resolver.py
    ├── entity_linker.py
    ├── entity_resolver.py
    ├── anonymizer.py
    ├── placeholder.py
    └── pipeline.py                     # PipelineConfig + Manifest dataclasses

src/piighost/cli/                       NEW sub-package
└── __init__.py                         # Typer app + entry-point main()

tests/config/                           NEW
├── __init__.py
├── fixtures/
│   ├── minimal.toml
│   ├── multi_detector.toml
│   └── invalid/
│       ├── unknown_key.toml
│       ├── bad_threshold.toml
│       ├── bad_regex.toml
│       └── empty_detectors.toml
├── test_models.py                      # Pydantic validation
├── test_loader.py                      # load_config + build_pipeline
├── test_manifest.py
└── test_schema.py

tests/cli/                              NEW
├── __init__.py
└── test_cli.py

Modified component files (each gains Config ClassVar + from_config classmethod):
- src/piighost/detector/base.py         # RegexDetector
- src/piighost/detector/gliner2.py
- src/piighost/detector/spacy.py
- src/piighost/detector/transformers.py
- src/piighost/detector/llm.py
- src/piighost/detector/chunked.py
- src/piighost/resolver/span.py
- src/piighost/resolver/entity.py
- src/piighost/linker/entity.py
- src/piighost/anonymizer.py
- src/piighost/placeholder.py           # label/redact/mask families
- src/piighost/ph_factory/faker.py
- src/piighost/ph_factory/faker_hash.py

pyproject.toml: new optional-dep group `config`, new entry-point `piighost`
docs/en/configuration/toml.md and docs/fr/configuration/toml.md: TOML reference
```

---

## Phase 1: Dependencies and foundation

### Task 1: Add `config` optional dependency group

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the optional dependency group**

Edit `pyproject.toml`. Add this block right after the existing `langchain = [...]` block in `[project.optional-dependencies]`:

```toml
config = [
    "pydantic>=2.6",
    "typer>=0.12",
    "tomli>=2.0; python_version < '3.11'",
]
```

Also update the `all` entry to include `config`:

```toml
all = [
    "piighost[gliner2,langchain,faker,cache,client,spacy,transformers,llm,sqlalchemy,langfuse,opik,config]",
]
```

- [ ] **Step 2: Add `config` to dev `[dependency-groups]`**

In `[dependency-groups]`, add:

```toml
config = [
    "pydantic>=2.6",
    "typer>=0.12",
    "tomli>=2.0; python_version < '3.11'",
]
```

- [ ] **Step 3: Update dev group to include config**

Add `"pydantic>=2.6"`, `"typer>=0.12"`, `"tomli>=2.0; python_version < '3.11'"` to the existing `dev = [...]` list so that `uv sync` installs them by default for development.

- [ ] **Step 4: Sync and verify**

Run: `uv sync --group dev --group config`
Expected: Resolves and installs pydantic + typer + tomli (on 3.10) without errors.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build(deps): add config optional dependency group (pydantic, typer, tomli)"
```

---

### Task 2: Create `piighost.config` package skeleton with `ConfigError`

**Files:**
- Create: `src/piighost/config/__init__.py`
- Create: `src/piighost/config/errors.py`
- Create: `tests/config/__init__.py`
- Create: `tests/config/test_errors.py`

- [ ] **Step 1: Write the failing test**

Create `tests/config/test_errors.py`:

```python
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from piighost.config.errors import ConfigError


class _Sample(BaseModel):
    x: int


def test_config_error_is_an_exception():
    err = ConfigError("boom")
    assert isinstance(err, Exception)
    assert str(err) == "boom"


def test_from_pydantic_renders_dotted_path_and_reason():
    try:
        _Sample.model_validate({"x": "not-an-int"})
    except ValidationError as e:
        ce = ConfigError.from_pydantic(e, Path("/tmp/conf.toml"))
    assert "/tmp/conf.toml" in str(ce)
    assert "x" in str(ce)
    assert "int" in str(ce).lower()


def test_from_pydantic_handles_nested_paths():
    class Inner(BaseModel):
        n: int

    class Outer(BaseModel):
        inner: Inner

    try:
        Outer.model_validate({"inner": {"n": "bad"}})
    except ValidationError as e:
        ce = ConfigError.from_pydantic(e, Path("/tmp/c.toml"))
    assert "inner.n" in str(ce)
```

Also create empty `tests/config/__init__.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/config/test_errors.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'piighost.config'`

- [ ] **Step 3: Implement the package and errors module**

Create `src/piighost/config/__init__.py`:

```python
"""Declarative TOML configuration for piighost pipelines.

Public API:

* :func:`load_config` parses a TOML file into a validated ``PipelineConfig``
  without instantiating any component.
* :func:`build_pipeline` turns a ``PipelineConfig`` into a working
  ``ThreadAnonymizationPipeline`` and a ``PipelineManifest`` describing
  what was built.
* :func:`load_pipeline` is the ``load_config`` + ``build_pipeline`` convenience.
* :func:`export_schema` dumps the JSON Schema of ``PipelineConfig`` for
  tooling (CLI, future configuration UI).
* :class:`ConfigError` is the single exception type raised by this module.
"""

from piighost.config.errors import ConfigError

__all__ = ["ConfigError"]
```

Create `src/piighost/config/errors.py`:

```python
"""Errors raised by :mod:`piighost.config`."""

from pathlib import Path

from pydantic import ValidationError


class ConfigError(Exception):
    """Raised when a TOML configuration cannot be loaded into a pipeline."""

    @classmethod
    def from_pydantic(cls, err: ValidationError, path: Path) -> "ConfigError":
        """Translate a Pydantic ``ValidationError`` into a readable message.

        Each Pydantic error gets a line of the form ``loc.dotted.path: reason``
        where ``loc.dotted.path`` is the TOML key location (e.g.
        ``detectors[1].threshold``).
        """
        lines = [f"invalid configuration in {path}"]
        for error in err.errors():
            loc = ".".join(_render_loc_part(p) for p in error["loc"])
            lines.append(f"  {loc}: {error['msg']}")
        return cls("\n".join(lines))


def _render_loc_part(part: object) -> str:
    """Render a Pydantic location segment (string or int index)."""
    if isinstance(part, int):
        return f"[{part}]"
    return str(part)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/config/test_errors.py -v`
Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
git add src/piighost/config/__init__.py src/piighost/config/errors.py tests/config/__init__.py tests/config/test_errors.py
git commit -m "feat(config): add ConfigError and Pydantic translator"
```

---

## Phase 2: Pydantic models per stage

### Task 3: Common base config model

**Files:**
- Create: `src/piighost/config/models/__init__.py`
- Create: `src/piighost/config/models/common.py`
- Create: `tests/config/test_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/config/test_models.py`:

```python
import pytest
from pydantic import ValidationError

from piighost.config.models.common import _ComponentConfig


class _Sample(_ComponentConfig):
    x: int


def test_component_config_forbids_extra_keys():
    with pytest.raises(ValidationError) as exc:
        _Sample.model_validate({"x": 1, "rogue": True})
    assert "rogue" in str(exc.value)


def test_component_config_is_frozen():
    s = _Sample.model_validate({"x": 1})
    with pytest.raises(ValidationError):
        s.x = 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/config/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement common.py**

Create `src/piighost/config/models/__init__.py` (empty file).

Create `src/piighost/config/models/common.py`:

```python
"""Shared base config model."""

from pydantic import BaseModel, ConfigDict


class _ComponentConfig(BaseModel):
    """Common base for all component configuration models.

    Forbids unknown keys and freezes instances so that validated config
    cannot be mutated by callers. ``protected_namespaces`` is emptied
    because several detector configs declare a ``model`` field (HF/spaCy
    model identifier), which would otherwise collide with the default
    ``model_`` Pydantic protected namespace.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        protected_namespaces=(),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/config/test_models.py -v`
Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

```bash
git add src/piighost/config/models/
git commit -m "feat(config): add _ComponentConfig base model"
```

---

### Task 4: Detector configs (discriminated union)

**Files:**
- Create: `src/piighost/config/models/detector.py`
- Modify: `tests/config/test_models.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/config/test_models.py`:

```python
from piighost.config.models.detector import (
    ChunkedDetectorConfig,
    DetectorConfig,
    Gliner2DetectorConfig,
    LLMDetectorConfig,
    RegexDetectorConfig,
    SpacyDetectorConfig,
    TransformersDetectorConfig,
)
from pydantic import TypeAdapter


_DETECTOR_ADAPTER = TypeAdapter(DetectorConfig)


def test_regex_detector_parses():
    cfg = _DETECTOR_ADAPTER.validate_python(
        {"type": "regex", "name": "common", "patterns": {"EMAIL": r"\S+@\S+"}}
    )
    assert isinstance(cfg, RegexDetectorConfig)
    assert cfg.name == "common"
    assert cfg.patterns == {"EMAIL": r"\S+@\S+"}


def test_gliner2_detector_parses_with_threshold_bounds():
    cfg = _DETECTOR_ADAPTER.validate_python(
        {
            "type": "gliner2",
            "model": "fastino/gliner2-multi-v1",
            "threshold": 0.5,
            "labels": ["person"],
        }
    )
    assert isinstance(cfg, Gliner2DetectorConfig)


def test_gliner2_rejects_threshold_above_one():
    with pytest.raises(ValidationError):
        _DETECTOR_ADAPTER.validate_python(
            {
                "type": "gliner2",
                "model": "x",
                "threshold": 1.5,
                "labels": ["person"],
            }
        )


def test_gliner2_rejects_empty_labels():
    with pytest.raises(ValidationError):
        _DETECTOR_ADAPTER.validate_python(
            {"type": "gliner2", "model": "x", "labels": []}
        )


def test_unknown_detector_type_is_rejected():
    with pytest.raises(ValidationError) as exc:
        _DETECTOR_ADAPTER.validate_python({"type": "http", "endpoint": "x"})
    # Discriminator error names the bad tag.
    assert "http" in str(exc.value)


def test_chunked_detector_nests_inner():
    cfg = _DETECTOR_ADAPTER.validate_python(
        {
            "type": "chunked",
            "chunk_size": 1000,
            "inner": {
                "type": "regex",
                "patterns": {"EMAIL": r"\S+@\S+"},
            },
        }
    )
    assert isinstance(cfg, ChunkedDetectorConfig)
    assert isinstance(cfg.inner, RegexDetectorConfig)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/config/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError` on `piighost.config.models.detector`.

- [ ] **Step 3: Implement detector.py**

Create `src/piighost/config/models/detector.py`:

```python
"""Detector configuration models (discriminated union on ``type``)."""

from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.config.models.common import _ComponentConfig


class RegexDetectorConfig(_ComponentConfig):
    type: Literal["regex"]
    name: str | None = None
    patterns: dict[str, str] = Field(min_length=1)


class Gliner2DetectorConfig(_ComponentConfig):
    type: Literal["gliner2"]
    name: str | None = None
    model: str
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    labels: list[str] = Field(min_length=1)
    flat_ner: bool = True


class SpacyDetectorConfig(_ComponentConfig):
    type: Literal["spacy"]
    name: str | None = None
    model: str
    labels: list[str] = Field(min_length=1)


class TransformersDetectorConfig(_ComponentConfig):
    type: Literal["transformers"]
    name: str | None = None
    model: str
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class LLMDetectorConfig(_ComponentConfig):
    type: Literal["llm"]
    name: str | None = None
    provider: str
    model: str
    labels: list[str] = Field(min_length=1)


class ChunkedDetectorConfig(_ComponentConfig):
    type: Literal["chunked"]
    name: str | None = None
    chunk_size: int = Field(ge=1)
    overlap: int = Field(default=0, ge=0)
    inner: "DetectorConfig"


DetectorConfig = Annotated[
    RegexDetectorConfig
    | Gliner2DetectorConfig
    | SpacyDetectorConfig
    | TransformersDetectorConfig
    | LLMDetectorConfig
    | ChunkedDetectorConfig,
    Discriminator("type"),
]


# Resolve the self-reference in ChunkedDetectorConfig.inner.
ChunkedDetectorConfig.model_rebuild()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/config/test_models.py -v`
Expected: PASS, 8 tests total.

- [ ] **Step 5: Commit**

```bash
git add src/piighost/config/models/detector.py tests/config/test_models.py
git commit -m "feat(config): add detector configuration models (discriminated union)"
```

---

### Task 5: Span resolver, entity linker, entity resolver configs

**Files:**
- Create: `src/piighost/config/models/span_resolver.py`
- Create: `src/piighost/config/models/entity_linker.py`
- Create: `src/piighost/config/models/entity_resolver.py`
- Modify: `tests/config/test_models.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/config/test_models.py`:

```python
from piighost.config.models.span_resolver import (
    ConfidenceSpanResolverConfig,
    DisabledSpanResolverConfig,
    SpanResolverConfig,
)
from piighost.config.models.entity_linker import (
    DisabledEntityLinkerConfig,
    EntityLinkerConfig,
    ExactEntityLinkerConfig,
)
from piighost.config.models.entity_resolver import (
    DisabledEntityResolverConfig,
    EntityResolverConfig,
    FuzzyEntityResolverConfig,
    MergeEntityResolverConfig,
)


_SPAN_ADAPTER = TypeAdapter(SpanResolverConfig)
_LINKER_ADAPTER = TypeAdapter(EntityLinkerConfig)
_ENTITY_ADAPTER = TypeAdapter(EntityResolverConfig)


def test_span_resolver_confidence():
    cfg = _SPAN_ADAPTER.validate_python({"type": "confidence"})
    assert isinstance(cfg, ConfidenceSpanResolverConfig)


def test_span_resolver_disabled():
    cfg = _SPAN_ADAPTER.validate_python({"type": "disabled"})
    assert isinstance(cfg, DisabledSpanResolverConfig)


def test_entity_linker_exact():
    cfg = _LINKER_ADAPTER.validate_python({"type": "exact"})
    assert isinstance(cfg, ExactEntityLinkerConfig)


def test_entity_resolver_fuzzy_threshold_bounds():
    cfg = _ENTITY_ADAPTER.validate_python({"type": "fuzzy", "threshold": 0.85})
    assert isinstance(cfg, FuzzyEntityResolverConfig)
    assert cfg.threshold == 0.85
    with pytest.raises(ValidationError):
        _ENTITY_ADAPTER.validate_python({"type": "fuzzy", "threshold": 1.5})


def test_entity_resolver_merge_default():
    cfg = _ENTITY_ADAPTER.validate_python({"type": "merge"})
    assert isinstance(cfg, MergeEntityResolverConfig)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/config/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the three models**

Create `src/piighost/config/models/span_resolver.py`:

```python
"""Span conflict resolver configuration models."""

from typing import Annotated, Literal

from pydantic import Discriminator

from piighost.config.models.common import _ComponentConfig


class ConfidenceSpanResolverConfig(_ComponentConfig):
    type: Literal["confidence"] = "confidence"


class DisabledSpanResolverConfig(_ComponentConfig):
    type: Literal["disabled"]


SpanResolverConfig = Annotated[
    ConfidenceSpanResolverConfig | DisabledSpanResolverConfig,
    Discriminator("type"),
]
```

Create `src/piighost/config/models/entity_linker.py`:

```python
"""Entity linker configuration models."""

from typing import Annotated, Literal

from pydantic import Discriminator

from piighost.config.models.common import _ComponentConfig


class ExactEntityLinkerConfig(_ComponentConfig):
    type: Literal["exact"] = "exact"


class DisabledEntityLinkerConfig(_ComponentConfig):
    type: Literal["disabled"]


EntityLinkerConfig = Annotated[
    ExactEntityLinkerConfig | DisabledEntityLinkerConfig,
    Discriminator("type"),
]
```

Create `src/piighost/config/models/entity_resolver.py`:

```python
"""Entity conflict resolver configuration models."""

from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.config.models.common import _ComponentConfig


class MergeEntityResolverConfig(_ComponentConfig):
    type: Literal["merge"] = "merge"


class FuzzyEntityResolverConfig(_ComponentConfig):
    type: Literal["fuzzy"]
    threshold: float = Field(default=0.85, ge=0.0, le=1.0)


class DisabledEntityResolverConfig(_ComponentConfig):
    type: Literal["disabled"]


EntityResolverConfig = Annotated[
    MergeEntityResolverConfig
    | FuzzyEntityResolverConfig
    | DisabledEntityResolverConfig,
    Discriminator("type"),
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/config/test_models.py -v`
Expected: PASS, 13 tests total.

- [ ] **Step 5: Commit**

```bash
git add src/piighost/config/models/span_resolver.py src/piighost/config/models/entity_linker.py src/piighost/config/models/entity_resolver.py tests/config/test_models.py
git commit -m "feat(config): add span/linker/entity resolver configuration models"
```

---

### Task 6: Anonymizer and placeholder factory configs

**Files:**
- Create: `src/piighost/config/models/placeholder.py`
- Create: `src/piighost/config/models/anonymizer.py`
- Modify: `tests/config/test_models.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/config/test_models.py`:

```python
from piighost.config.models.anonymizer import (
    AnonymizerConfig,
    DefaultAnonymizerConfig,
)
from piighost.config.models.placeholder import (
    FakerCounterPlaceholderConfig,
    LabelCounterPlaceholderConfig,
    MaskPlaceholderConfig,
    PlaceholderFactoryConfig,
)


_PLACEHOLDER_ADAPTER = TypeAdapter(PlaceholderFactoryConfig)


def test_label_counter_placeholder_default():
    cfg = _PLACEHOLDER_ADAPTER.validate_python({"type": "label_counter"})
    assert isinstance(cfg, LabelCounterPlaceholderConfig)


def test_mask_placeholder_with_char():
    cfg = _PLACEHOLDER_ADAPTER.validate_python({"type": "mask", "mask_char": "*"})
    assert isinstance(cfg, MaskPlaceholderConfig)
    assert cfg.mask_char == "*"


def test_faker_counter_placeholder_locale():
    cfg = _PLACEHOLDER_ADAPTER.validate_python(
        {"type": "faker_counter", "locale": "fr_FR"}
    )
    assert isinstance(cfg, FakerCounterPlaceholderConfig)
    assert cfg.locale == "fr_FR"


def test_anonymizer_default_includes_placeholder_factory():
    cfg = DefaultAnonymizerConfig.model_validate(
        {
            "type": "default",
            "placeholder_factory": {"type": "label_counter"},
        }
    )
    assert isinstance(cfg.placeholder_factory, LabelCounterPlaceholderConfig)


def test_anonymizer_placeholder_defaults_to_label_counter():
    cfg = DefaultAnonymizerConfig.model_validate({"type": "default"})
    assert isinstance(cfg.placeholder_factory, LabelCounterPlaceholderConfig)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/config/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement placeholder.py and anonymizer.py**

Create `src/piighost/config/models/placeholder.py`:

```python
"""Placeholder factory configuration models."""

from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.config.models.common import _ComponentConfig


class LabelCounterPlaceholderConfig(_ComponentConfig):
    type: Literal["label_counter"] = "label_counter"


class LabelHashPlaceholderConfig(_ComponentConfig):
    type: Literal["label_hash"]
    hash_length: int = Field(default=8, ge=4, le=64)


class LabelPlaceholderConfig(_ComponentConfig):
    type: Literal["label"]


class MaskPlaceholderConfig(_ComponentConfig):
    type: Literal["mask"]
    mask_char: str = Field(default="*", min_length=1, max_length=1)


class RedactCounterPlaceholderConfig(_ComponentConfig):
    type: Literal["redact_counter"]


class RedactHashPlaceholderConfig(_ComponentConfig):
    type: Literal["redact_hash"]
    hash_length: int = Field(default=8, ge=4, le=64)


class RedactPlaceholderConfig(_ComponentConfig):
    type: Literal["redact"]


class FakerCounterPlaceholderConfig(_ComponentConfig):
    type: Literal["faker_counter"]
    locale: str = "en_US"


class FakerHashPlaceholderConfig(_ComponentConfig):
    type: Literal["faker_hash"]
    locale: str = "en_US"
    hash_length: int = Field(default=8, ge=4, le=64)


class FakerPlaceholderConfig(_ComponentConfig):
    type: Literal["faker"]
    locale: str = "en_US"


PlaceholderFactoryConfig = Annotated[
    LabelCounterPlaceholderConfig
    | LabelHashPlaceholderConfig
    | LabelPlaceholderConfig
    | MaskPlaceholderConfig
    | RedactCounterPlaceholderConfig
    | RedactHashPlaceholderConfig
    | RedactPlaceholderConfig
    | FakerCounterPlaceholderConfig
    | FakerHashPlaceholderConfig
    | FakerPlaceholderConfig,
    Discriminator("type"),
]
```

Create `src/piighost/config/models/anonymizer.py`:

```python
"""Anonymizer configuration models."""

from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.config.models.common import _ComponentConfig
from piighost.config.models.placeholder import (
    LabelCounterPlaceholderConfig,
    PlaceholderFactoryConfig,
)


class DefaultAnonymizerConfig(_ComponentConfig):
    type: Literal["default"] = "default"
    placeholder_factory: PlaceholderFactoryConfig = Field(
        default_factory=LabelCounterPlaceholderConfig
    )


AnonymizerConfig = Annotated[
    DefaultAnonymizerConfig,
    Discriminator("type"),
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/config/test_models.py -v`
Expected: PASS, 18 tests total.

- [ ] **Step 5: Commit**

```bash
git add src/piighost/config/models/placeholder.py src/piighost/config/models/anonymizer.py tests/config/test_models.py
git commit -m "feat(config): add anonymizer and placeholder factory configuration models"
```

---

### Task 7: Top-level `PipelineConfig` and `PipelineManifest`

**Files:**
- Create: `src/piighost/config/models/pipeline.py`
- Modify: `src/piighost/config/models/__init__.py`
- Modify: `tests/config/test_models.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/config/test_models.py`:

```python
from piighost.config.models.pipeline import PipelineConfig, PipelineMeta


def test_pipeline_config_requires_at_least_one_detector():
    with pytest.raises(ValidationError):
        PipelineConfig.model_validate({"detectors": []})


def test_pipeline_config_applies_defaults():
    cfg = PipelineConfig.model_validate(
        {
            "detectors": [
                {"type": "regex", "patterns": {"EMAIL": r"\S+@\S+"}},
            ],
        }
    )
    assert isinstance(cfg.span_resolver, ConfidenceSpanResolverConfig)
    assert isinstance(cfg.entity_linker, ExactEntityLinkerConfig)
    assert isinstance(cfg.entity_resolver, MergeEntityResolverConfig)
    assert isinstance(cfg.anonymizer, DefaultAnonymizerConfig)
    assert isinstance(cfg.pipeline, PipelineMeta)
    assert cfg.pipeline.schema_version == 1


def test_pipeline_meta_optional_name():
    cfg = PipelineConfig.model_validate(
        {
            "pipeline": {"name": "demo"},
            "detectors": [
                {"type": "regex", "patterns": {"EMAIL": r"\S+@\S+"}},
            ],
        }
    )
    assert cfg.pipeline.name == "demo"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/config/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement pipeline.py and update package exports**

Create `src/piighost/config/models/pipeline.py`:

```python
"""Top-level pipeline configuration and manifest."""

from typing import Literal

from pydantic import Field

from piighost.config.models.anonymizer import (
    AnonymizerConfig,
    DefaultAnonymizerConfig,
)
from piighost.config.models.common import _ComponentConfig
from piighost.config.models.detector import DetectorConfig
from piighost.config.models.entity_linker import (
    EntityLinkerConfig,
    ExactEntityLinkerConfig,
)
from piighost.config.models.entity_resolver import (
    EntityResolverConfig,
    MergeEntityResolverConfig,
)
from piighost.config.models.span_resolver import (
    ConfidenceSpanResolverConfig,
    SpanResolverConfig,
)


class PipelineMeta(_ComponentConfig):
    """Free-text metadata for the pipeline. Exposed by ``/v1/labels``."""

    name: str | None = None
    description: str | None = None
    schema_version: Literal[1] = 1


class PipelineConfig(_ComponentConfig):
    """Root model for a piighost pipeline TOML configuration."""

    pipeline: PipelineMeta = Field(default_factory=PipelineMeta)
    detectors: list[DetectorConfig] = Field(min_length=1)
    span_resolver: SpanResolverConfig = Field(
        default_factory=ConfidenceSpanResolverConfig
    )
    entity_linker: EntityLinkerConfig = Field(default_factory=ExactEntityLinkerConfig)
    entity_resolver: EntityResolverConfig = Field(
        default_factory=MergeEntityResolverConfig
    )
    anonymizer: AnonymizerConfig = Field(default_factory=DefaultAnonymizerConfig)
```

Update `src/piighost/config/models/__init__.py` to re-export the top-level models:

```python
"""Pydantic configuration models for piighost pipelines."""

from piighost.config.models.pipeline import PipelineConfig, PipelineMeta

__all__ = ["PipelineConfig", "PipelineMeta"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/config/test_models.py -v`
Expected: PASS, 21 tests total.

- [ ] **Step 5: Commit**

```bash
git add src/piighost/config/models/pipeline.py src/piighost/config/models/__init__.py tests/config/test_models.py
git commit -m "feat(config): add top-level PipelineConfig and PipelineMeta"
```

---

## Phase 3: Component-config pairing

> **Note for executor:** Each existing component class gains a `Config: ClassVar` and a `from_config` classmethod. The component's runtime behavior is untouched. Tests check that `from_config(cfg)` produces a working instance equivalent to direct construction.

### Task 8: Wire `RegexDetector.from_config`

**Files:**
- Modify: `src/piighost/detector/base.py` (the `RegexDetector` class around lines 201-272)
- Create: `tests/config/test_from_config_detectors.py`

- [ ] **Step 1: Write the failing test**

Create `tests/config/test_from_config_detectors.py`:

```python
import pytest

from piighost.config.models.detector import RegexDetectorConfig
from piighost.detector.base import RegexDetector


@pytest.mark.asyncio
async def test_regex_detector_from_config_produces_working_instance():
    cfg = RegexDetectorConfig(
        type="regex",
        name="common",
        patterns={"EMAIL": r"[a-z]+@[a-z]+\.[a-z]+"},
    )
    detector = RegexDetector.from_config(cfg)
    assert isinstance(detector, RegexDetector)

    detections = await detector.detect("contact: alice@example.com")
    assert len(detections) == 1
    assert detections[0].label == "EMAIL"
    assert detections[0].text == "alice@example.com"


def test_regex_detector_config_classvar_points_to_config_model():
    assert RegexDetector.Config is RegexDetectorConfig
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/config/test_from_config_detectors.py -v`
Expected: FAIL with `AttributeError: type object 'RegexDetector' has no attribute 'Config'`.

- [ ] **Step 3: Implement on RegexDetector**

Edit `src/piighost/detector/base.py`. Modify the `RegexDetector` class (currently at lines 201-272):

1. At the top of the file, add imports:

```python
from typing import ClassVar, TYPE_CHECKING

if TYPE_CHECKING:
    from piighost.config.models.detector import RegexDetectorConfig
```

2. Inside `RegexDetector`, add the `Config` ClassVar and the `from_config` classmethod (place right after the existing class docstring, before the `__init__`):

```python
    Config: ClassVar[type["RegexDetectorConfig"]]

    @classmethod
    def from_config(cls, cfg: "RegexDetectorConfig") -> "RegexDetector":
        """Build a ``RegexDetector`` from its validated configuration."""
        return cls(patterns=dict(cfg.patterns))
```

3. At the very bottom of the file, after all class definitions, resolve the ClassVar:

```python
from piighost.config.models.detector import RegexDetectorConfig  # noqa: E402

RegexDetector.Config = RegexDetectorConfig
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/config/test_from_config_detectors.py -v`
Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

```bash
git add src/piighost/detector/base.py tests/config/test_from_config_detectors.py
git commit -m "feat(detector): add Config + from_config to RegexDetector"
```

---

### Task 9: Wire `Gliner2Detector.from_config`

**Files:**
- Modify: `src/piighost/detector/gliner2.py`
- Modify: `tests/config/test_from_config_detectors.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/config/test_from_config_detectors.py`:

```python
@pytest.mark.integration
def test_gliner2_detector_config_classvar():
    from piighost.config.models.detector import Gliner2DetectorConfig
    from piighost.detector.gliner2 import Gliner2Detector

    assert Gliner2Detector.Config is Gliner2DetectorConfig
```

(The actual `from_config` smoke test that loads GLiNER2 lives in the integration-marked loader tests later. Here we only verify the wiring exists so the test runs without the heavy model.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/config/test_from_config_detectors.py -v -m integration`
Expected: FAIL with `AttributeError`.

- [ ] **Step 3: Implement on Gliner2Detector**

Edit `src/piighost/detector/gliner2.py`. Add at the top after the existing imports:

```python
from typing import ClassVar, TYPE_CHECKING

if TYPE_CHECKING:
    from piighost.config.models.detector import Gliner2DetectorConfig
```

Inside the `Gliner2Detector` class, add after the existing class attributes (`model: GLiNER2`, `threshold: float`, `flat_ner: bool`):

```python
    Config: ClassVar[type["Gliner2DetectorConfig"]]

    @classmethod
    def from_config(cls, cfg: "Gliner2DetectorConfig") -> "Gliner2Detector":
        """Build a ``Gliner2Detector`` from its validated configuration.

        Loads the model with ``GLiNER2.from_pretrained``. Network access
        may be required the first time a given model name is loaded.
        """
        model = GLiNER2.from_pretrained(cfg.model)
        return cls(
            model=model,
            labels=list(cfg.labels),
            threshold=cfg.threshold,
            flat_ner=cfg.flat_ner,
        )
```

At the bottom of the file:

```python
from piighost.config.models.detector import Gliner2DetectorConfig  # noqa: E402

Gliner2Detector.Config = Gliner2DetectorConfig
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/config/test_from_config_detectors.py -v -m integration`
Expected: PASS for the integration-marked test.

Also confirm non-integration tests still pass:

Run: `uv run pytest tests/config/ -v`
Expected: All previous tests still PASS.

- [ ] **Step 5: Commit**

```bash
git add src/piighost/detector/gliner2.py tests/config/test_from_config_detectors.py
git commit -m "feat(detector): add Config + from_config to Gliner2Detector"
```

---

### Task 10: Wire remaining detectors (`SpacyDetector`, `TransformersDetector`, `LLMDetector`, `ChunkedDetector`)

**Files:**
- Modify: `src/piighost/detector/spacy.py`
- Modify: `src/piighost/detector/transformers.py`
- Modify: `src/piighost/detector/llm.py`
- Modify: `src/piighost/detector/chunked.py`
- Modify: `tests/config/test_from_config_detectors.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/config/test_from_config_detectors.py`:

```python
def test_spacy_detector_config_classvar():
    from piighost.config.models.detector import SpacyDetectorConfig
    from piighost.detector.spacy import SpacyDetector

    assert SpacyDetector.Config is SpacyDetectorConfig


def test_transformers_detector_config_classvar():
    from piighost.config.models.detector import TransformersDetectorConfig
    from piighost.detector.transformers import TransformersDetector

    assert TransformersDetector.Config is TransformersDetectorConfig


def test_llm_detector_config_classvar():
    from piighost.config.models.detector import LLMDetectorConfig
    from piighost.detector.llm import LLMDetector

    assert LLMDetector.Config is LLMDetectorConfig


def test_chunked_detector_config_classvar():
    from piighost.config.models.detector import ChunkedDetectorConfig
    from piighost.detector.chunked import ChunkedDetector

    assert ChunkedDetector.Config is ChunkedDetectorConfig


@pytest.mark.asyncio
async def test_chunked_detector_from_config_wraps_inner_regex():
    from piighost.config.models.detector import (
        ChunkedDetectorConfig,
        RegexDetectorConfig,
    )
    from piighost.detector.chunked import ChunkedDetector

    cfg = ChunkedDetectorConfig(
        type="chunked",
        chunk_size=1000,
        inner=RegexDetectorConfig(
            type="regex", patterns={"EMAIL": r"[a-z]+@[a-z]+\.[a-z]+"}
        ),
    )
    detector = ChunkedDetector.from_config(cfg)
    detections = await detector.detect("contact: alice@example.com")
    assert len(detections) == 1
    assert detections[0].label == "EMAIL"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/config/test_from_config_detectors.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `from_config` for each detector**

For each file, follow the same pattern as Task 9: add `from typing import ClassVar, TYPE_CHECKING`, add a `TYPE_CHECKING` import of the matching `*Config`, add `Config: ClassVar[...]` and `from_config` inside the class, and assign `Cls.Config = ...Config` at the bottom of the file.

`src/piighost/detector/spacy.py` — `from_config`:

```python
    @classmethod
    def from_config(cls, cfg: "SpacyDetectorConfig") -> "SpacyDetector":
        import spacy
        nlp = spacy.load(cfg.model)
        return cls(nlp=nlp, labels=list(cfg.labels))
```

(Adjust the constructor signature to match the actual `SpacyDetector.__init__` in your file. Read `src/piighost/detector/spacy.py` first and use the parameter names it expects.)

`src/piighost/detector/transformers.py` — `from_config`:

```python
    @classmethod
    def from_config(cls, cfg: "TransformersDetectorConfig") -> "TransformersDetector":
        from transformers import pipeline
        nlp = pipeline("ner", model=cfg.model)
        return cls(nlp=nlp, threshold=cfg.threshold)
```

(Same caveat: align the constructor with the existing signature.)

`src/piighost/detector/llm.py` — `from_config`:

```python
    @classmethod
    def from_config(cls, cfg: "LLMDetectorConfig") -> "LLMDetector":
        # API key is read from env (PIIGHOST_LLM_API_KEY) by the underlying
        # provider client, not from the TOML.
        from langchain_core.language_models import init_chat_model
        llm = init_chat_model(cfg.model, model_provider=cfg.provider)
        return cls(llm=llm, labels=list(cfg.labels))
```

`src/piighost/detector/chunked.py` — `from_config`:

```python
    @classmethod
    def from_config(cls, cfg: "ChunkedDetectorConfig") -> "ChunkedDetector":
        from piighost.config.builders import build_detector

        inner = build_detector(cfg.inner)
        return cls(inner=inner, chunk_size=cfg.chunk_size, overlap=cfg.overlap)
```

(Note: `ChunkedDetector` references `build_detector` from `piighost.config.builders`, created in Task 12. Until then, the integration test for chunked will fail. That is acceptable — tasks build forward.)

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/config/test_from_config_detectors.py -v`
Expected: ClassVar tests PASS. The `chunked` async test will fail until Task 12.

Mark it accordingly with `@pytest.mark.skip(reason="depends on builders module, see Task 12")` so the suite stays green meanwhile.

- [ ] **Step 5: Commit**

```bash
git add src/piighost/detector/spacy.py src/piighost/detector/transformers.py src/piighost/detector/llm.py src/piighost/detector/chunked.py tests/config/test_from_config_detectors.py
git commit -m "feat(detector): add Config + from_config to spacy/transformers/llm/chunked detectors"
```

---

### Task 11: Wire span resolver, entity linker, entity resolver, anonymizer, and placeholder factories

**Files:**
- Modify: `src/piighost/resolver/span.py`
- Modify: `src/piighost/resolver/entity.py`
- Modify: `src/piighost/linker/entity.py`
- Modify: `src/piighost/anonymizer.py`
- Modify: `src/piighost/placeholder.py`
- Modify: `src/piighost/ph_factory/faker.py`
- Modify: `src/piighost/ph_factory/faker_hash.py`
- Create: `tests/config/test_from_config_components.py`

- [ ] **Step 1: Write the failing test**

Create `tests/config/test_from_config_components.py`:

```python
import pytest

from piighost.config.models.anonymizer import DefaultAnonymizerConfig
from piighost.config.models.entity_linker import (
    DisabledEntityLinkerConfig,
    ExactEntityLinkerConfig,
)
from piighost.config.models.entity_resolver import (
    DisabledEntityResolverConfig,
    FuzzyEntityResolverConfig,
    MergeEntityResolverConfig,
)
from piighost.config.models.placeholder import (
    LabelCounterPlaceholderConfig,
    MaskPlaceholderConfig,
)
from piighost.config.models.span_resolver import (
    ConfidenceSpanResolverConfig,
    DisabledSpanResolverConfig,
)
from piighost.anonymizer import Anonymizer
from piighost.linker.entity import ExactEntityLinker, DisabledEntityLinker
from piighost.placeholder import (
    LabelCounterPlaceholderFactory,
    MaskPlaceholderFactory,
)
from piighost.resolver.entity import (
    DisabledEntityConflictResolver,
    FuzzyEntityConflictResolver,
    MergeEntityConflictResolver,
)
from piighost.resolver.span import (
    ConfidenceSpanConflictResolver,
    DisabledSpanConflictResolver,
)


def test_span_resolver_from_config_confidence():
    r = ConfidenceSpanConflictResolver.from_config(ConfidenceSpanResolverConfig())
    assert isinstance(r, ConfidenceSpanConflictResolver)


def test_span_resolver_from_config_disabled():
    r = DisabledSpanConflictResolver.from_config(
        DisabledSpanResolverConfig(type="disabled")
    )
    assert isinstance(r, DisabledSpanConflictResolver)


def test_entity_linker_from_config_exact():
    linker = ExactEntityLinker.from_config(ExactEntityLinkerConfig())
    assert isinstance(linker, ExactEntityLinker)


def test_entity_linker_from_config_disabled():
    linker = DisabledEntityLinker.from_config(
        DisabledEntityLinkerConfig(type="disabled")
    )
    assert isinstance(linker, DisabledEntityLinker)


def test_entity_resolver_from_config_merge():
    r = MergeEntityConflictResolver.from_config(MergeEntityResolverConfig())
    assert isinstance(r, MergeEntityConflictResolver)


def test_entity_resolver_from_config_fuzzy_threshold():
    cfg = FuzzyEntityResolverConfig(type="fuzzy", threshold=0.9)
    r = FuzzyEntityConflictResolver.from_config(cfg)
    assert isinstance(r, FuzzyEntityConflictResolver)
    assert r.threshold == 0.9


def test_entity_resolver_from_config_disabled():
    r = DisabledEntityConflictResolver.from_config(
        DisabledEntityResolverConfig(type="disabled")
    )
    assert isinstance(r, DisabledEntityConflictResolver)


def test_placeholder_factory_from_config_label_counter():
    f = LabelCounterPlaceholderFactory.from_config(LabelCounterPlaceholderConfig())
    assert isinstance(f, LabelCounterPlaceholderFactory)


def test_placeholder_factory_from_config_mask():
    f = MaskPlaceholderFactory.from_config(
        MaskPlaceholderConfig(type="mask", mask_char="#")
    )
    assert isinstance(f, MaskPlaceholderFactory)


def test_anonymizer_from_config_default():
    cfg = DefaultAnonymizerConfig(
        type="default",
        placeholder_factory=LabelCounterPlaceholderConfig(),
    )
    a = Anonymizer.from_config(cfg)
    assert isinstance(a, Anonymizer)
    assert isinstance(a.ph_factory, LabelCounterPlaceholderFactory)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/config/test_from_config_components.py -v`
Expected: FAIL with `AttributeError` on `from_config`.

- [ ] **Step 3: Implement `from_config` on each class**

For each class, apply the same pattern: add `Config: ClassVar[...]` ClassVar, add `from_config` classmethod, assign `Cls.Config = ...` at bottom of file.

`src/piighost/resolver/span.py` — for each class:

```python
    @classmethod
    def from_config(cls, cfg: "ConfidenceSpanResolverConfig") -> "ConfidenceSpanConflictResolver":
        return cls()

    # (DisabledSpanConflictResolver: same shape but cfg type DisabledSpanResolverConfig)
```

`src/piighost/resolver/entity.py`:

```python
    # MergeEntityConflictResolver
    @classmethod
    def from_config(cls, cfg: "MergeEntityResolverConfig") -> "MergeEntityConflictResolver":
        return cls()

    # FuzzyEntityConflictResolver (assumes its existing __init__ accepts `threshold`)
    @classmethod
    def from_config(cls, cfg: "FuzzyEntityResolverConfig") -> "FuzzyEntityConflictResolver":
        return cls(threshold=cfg.threshold)

    # DisabledEntityConflictResolver
    @classmethod
    def from_config(cls, cfg: "DisabledEntityResolverConfig") -> "DisabledEntityConflictResolver":
        return cls()
```

`src/piighost/linker/entity.py`:

```python
    # ExactEntityLinker
    @classmethod
    def from_config(cls, cfg: "ExactEntityLinkerConfig") -> "ExactEntityLinker":
        return cls()

    # DisabledEntityLinker
    @classmethod
    def from_config(cls, cfg: "DisabledEntityLinkerConfig") -> "DisabledEntityLinker":
        return cls()
```

`src/piighost/placeholder.py` — for each placeholder factory class:

```python
    # LabelCounterPlaceholderFactory
    @classmethod
    def from_config(cls, cfg: "LabelCounterPlaceholderConfig") -> "LabelCounterPlaceholderFactory":
        return cls()

    # LabelHashPlaceholderFactory
    @classmethod
    def from_config(cls, cfg: "LabelHashPlaceholderConfig") -> "LabelHashPlaceholderFactory":
        return cls(hash_length=cfg.hash_length)

    # LabelPlaceholderFactory
    @classmethod
    def from_config(cls, cfg: "LabelPlaceholderConfig") -> "LabelPlaceholderFactory":
        return cls()

    # MaskPlaceholderFactory (assumes existing __init__ accepts mask_char)
    @classmethod
    def from_config(cls, cfg: "MaskPlaceholderConfig") -> "MaskPlaceholderFactory":
        return cls(mask_char=cfg.mask_char)

    # RedactCounterPlaceholderFactory, RedactHashPlaceholderFactory, RedactPlaceholderFactory:
    # same shape as the Label* siblings above, swapping the config type and Cls.
```

`src/piighost/ph_factory/faker.py` (FakerPlaceholderFactory and FakerCounterPlaceholderFactory if defined there):

```python
    @classmethod
    def from_config(cls, cfg: "FakerPlaceholderConfig") -> "FakerPlaceholderFactory":
        return cls(locale=cfg.locale)

    # FakerCounterPlaceholderFactory
    @classmethod
    def from_config(cls, cfg: "FakerCounterPlaceholderConfig") -> "FakerCounterPlaceholderFactory":
        return cls(locale=cfg.locale)
```

`src/piighost/ph_factory/faker_hash.py`:

```python
    @classmethod
    def from_config(cls, cfg: "FakerHashPlaceholderConfig") -> "FakerHashPlaceholderFactory":
        return cls(locale=cfg.locale, hash_length=cfg.hash_length)
```

`src/piighost/anonymizer.py`:

```python
    Config: ClassVar[type["DefaultAnonymizerConfig"]]

    @classmethod
    def from_config(cls, cfg: "DefaultAnonymizerConfig") -> "Anonymizer":
        from piighost.config.builders import build_placeholder_factory

        ph_factory = build_placeholder_factory(cfg.placeholder_factory)
        return cls(ph_factory=ph_factory)
```

At each file's bottom, assign `Cls.Config = ...Config` for every class touched. Add the matching `TYPE_CHECKING` imports at each file's top.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/config/test_from_config_components.py -v`
Expected: PASS for all tests *except* `test_anonymizer_from_config_default`, which requires `build_placeholder_factory` from Task 12.

Mark `test_anonymizer_from_config_default` with `@pytest.mark.skip(reason="depends on builders module, see Task 12")` for now.

- [ ] **Step 5: Commit**

```bash
git add src/piighost/resolver/ src/piighost/linker/ src/piighost/anonymizer.py src/piighost/placeholder.py src/piighost/ph_factory/ tests/config/test_from_config_components.py
git commit -m "feat: add Config + from_config to resolvers, linkers, anonymizer, placeholder factories"
```

---

## Phase 4: Builders and loader

### Task 12: Builders mapping module

**Files:**
- Create: `src/piighost/config/builders.py`
- Create: `tests/config/test_builders.py`

- [ ] **Step 1: Write the failing test**

Create `tests/config/test_builders.py`:

```python
import pytest

from piighost.anonymizer import Anonymizer
from piighost.config.builders import (
    build_anonymizer,
    build_detector,
    build_entity_linker,
    build_entity_resolver,
    build_placeholder_factory,
    build_span_resolver,
)
from piighost.config.models.anonymizer import DefaultAnonymizerConfig
from piighost.config.models.detector import RegexDetectorConfig
from piighost.config.models.entity_linker import ExactEntityLinkerConfig
from piighost.config.models.entity_resolver import MergeEntityResolverConfig
from piighost.config.models.placeholder import LabelCounterPlaceholderConfig
from piighost.config.models.span_resolver import ConfidenceSpanResolverConfig
from piighost.detector.base import RegexDetector
from piighost.linker.entity import ExactEntityLinker
from piighost.placeholder import LabelCounterPlaceholderFactory
from piighost.resolver.entity import MergeEntityConflictResolver
from piighost.resolver.span import ConfidenceSpanConflictResolver


def test_build_detector_dispatch_on_config_type():
    cfg = RegexDetectorConfig(type="regex", patterns={"EMAIL": r"\S+@\S+"})
    d = build_detector(cfg)
    assert isinstance(d, RegexDetector)


def test_build_span_resolver_returns_confidence():
    r = build_span_resolver(ConfidenceSpanResolverConfig())
    assert isinstance(r, ConfidenceSpanConflictResolver)


def test_build_entity_linker_returns_exact():
    linker = build_entity_linker(ExactEntityLinkerConfig())
    assert isinstance(linker, ExactEntityLinker)


def test_build_entity_resolver_returns_merge():
    r = build_entity_resolver(MergeEntityResolverConfig())
    assert isinstance(r, MergeEntityConflictResolver)


def test_build_placeholder_factory_returns_label_counter():
    f = build_placeholder_factory(LabelCounterPlaceholderConfig())
    assert isinstance(f, LabelCounterPlaceholderFactory)


def test_build_anonymizer_includes_placeholder_factory():
    a = build_anonymizer(
        DefaultAnonymizerConfig(
            type="default",
            placeholder_factory=LabelCounterPlaceholderConfig(),
        )
    )
    assert isinstance(a, Anonymizer)
    assert isinstance(a.ph_factory, LabelCounterPlaceholderFactory)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/config/test_builders.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement builders.py**

Create `src/piighost/config/builders.py`:

```python
"""Type-mapping factories for ``piighost.config``.

Each ``build_*`` function dispatches on the concrete config class
(which Pydantic has already discriminated) to the matching component
class's ``from_config`` classmethod. Mappings are plain ``dict``s
keyed on the config type so dispatch is O(1) and trivially auditable.

Imports of the GLiNER / spaCy / transformers / LLM detector classes
are deferred to inside ``build_detector`` to keep ``piighost.config``
importable without their optional dependencies installed.
"""

from typing import TYPE_CHECKING

from pydantic import BaseModel

from piighost.anonymizer import Anonymizer
from piighost.config.models.anonymizer import DefaultAnonymizerConfig
from piighost.config.models.detector import (
    ChunkedDetectorConfig,
    Gliner2DetectorConfig,
    LLMDetectorConfig,
    RegexDetectorConfig,
    SpacyDetectorConfig,
    TransformersDetectorConfig,
)
from piighost.config.models.entity_linker import (
    DisabledEntityLinkerConfig,
    ExactEntityLinkerConfig,
)
from piighost.config.models.entity_resolver import (
    DisabledEntityResolverConfig,
    FuzzyEntityResolverConfig,
    MergeEntityResolverConfig,
)
from piighost.config.models.placeholder import (
    FakerCounterPlaceholderConfig,
    FakerHashPlaceholderConfig,
    FakerPlaceholderConfig,
    LabelCounterPlaceholderConfig,
    LabelHashPlaceholderConfig,
    LabelPlaceholderConfig,
    MaskPlaceholderConfig,
    RedactCounterPlaceholderConfig,
    RedactHashPlaceholderConfig,
    RedactPlaceholderConfig,
)
from piighost.config.models.span_resolver import (
    ConfidenceSpanResolverConfig,
    DisabledSpanResolverConfig,
)
from piighost.detector.base import RegexDetector
from piighost.linker.entity import DisabledEntityLinker, ExactEntityLinker
from piighost.placeholder import (
    LabelCounterPlaceholderFactory,
    LabelHashPlaceholderFactory,
    LabelPlaceholderFactory,
    MaskPlaceholderFactory,
    RedactCounterPlaceholderFactory,
    RedactHashPlaceholderFactory,
    RedactPlaceholderFactory,
)
from piighost.resolver.entity import (
    DisabledEntityConflictResolver,
    FuzzyEntityConflictResolver,
    MergeEntityConflictResolver,
)
from piighost.resolver.span import (
    ConfidenceSpanConflictResolver,
    DisabledSpanConflictResolver,
)

if TYPE_CHECKING:
    from piighost.detector.base import AnyDetector
    from piighost.linker.entity import BaseEntityLinker
    from piighost.placeholder import AnyPlaceholderFactory
    from piighost.resolver.entity import AnyEntityConflictResolver
    from piighost.resolver.span import AnySpanConflictResolver


_DETECTOR_BUILDERS: dict[type[BaseModel], object] = {
    RegexDetectorConfig: RegexDetector,
    ChunkedDetectorConfig: "lazy:chunked",  # resolved lazily below
    Gliner2DetectorConfig: "lazy:gliner2",
    SpacyDetectorConfig: "lazy:spacy",
    TransformersDetectorConfig: "lazy:transformers",
    LLMDetectorConfig: "lazy:llm",
}


def _resolve_lazy_detector(key: str) -> type:
    """Lazy-import optional-dep detectors so ``piighost.config`` stays light."""
    if key == "lazy:gliner2":
        from piighost.detector.gliner2 import Gliner2Detector
        return Gliner2Detector
    if key == "lazy:spacy":
        from piighost.detector.spacy import SpacyDetector
        return SpacyDetector
    if key == "lazy:transformers":
        from piighost.detector.transformers import TransformersDetector
        return TransformersDetector
    if key == "lazy:llm":
        from piighost.detector.llm import LLMDetector
        return LLMDetector
    if key == "lazy:chunked":
        from piighost.detector.chunked import ChunkedDetector
        return ChunkedDetector
    raise KeyError(key)


def build_detector(cfg: BaseModel) -> "AnyDetector":
    builder = _DETECTOR_BUILDERS[type(cfg)]
    cls = builder if not isinstance(builder, str) else _resolve_lazy_detector(builder)
    return cls.from_config(cfg)


_SPAN_RESOLVER_BUILDERS: dict[type[BaseModel], type] = {
    ConfidenceSpanResolverConfig: ConfidenceSpanConflictResolver,
    DisabledSpanResolverConfig: DisabledSpanConflictResolver,
}


def build_span_resolver(cfg: BaseModel) -> "AnySpanConflictResolver":
    return _SPAN_RESOLVER_BUILDERS[type(cfg)].from_config(cfg)


_LINKER_BUILDERS: dict[type[BaseModel], type] = {
    ExactEntityLinkerConfig: ExactEntityLinker,
    DisabledEntityLinkerConfig: DisabledEntityLinker,
}


def build_entity_linker(cfg: BaseModel) -> "BaseEntityLinker":
    return _LINKER_BUILDERS[type(cfg)].from_config(cfg)


_ENTITY_RESOLVER_BUILDERS: dict[type[BaseModel], type] = {
    MergeEntityResolverConfig: MergeEntityConflictResolver,
    FuzzyEntityResolverConfig: FuzzyEntityConflictResolver,
    DisabledEntityResolverConfig: DisabledEntityConflictResolver,
}


def build_entity_resolver(cfg: BaseModel) -> "AnyEntityConflictResolver":
    return _ENTITY_RESOLVER_BUILDERS[type(cfg)].from_config(cfg)


_PLACEHOLDER_BUILDERS: dict[type[BaseModel], object] = {
    LabelCounterPlaceholderConfig: LabelCounterPlaceholderFactory,
    LabelHashPlaceholderConfig: LabelHashPlaceholderFactory,
    LabelPlaceholderConfig: LabelPlaceholderFactory,
    MaskPlaceholderConfig: MaskPlaceholderFactory,
    RedactCounterPlaceholderConfig: RedactCounterPlaceholderFactory,
    RedactHashPlaceholderConfig: RedactHashPlaceholderFactory,
    RedactPlaceholderConfig: RedactPlaceholderFactory,
    FakerCounterPlaceholderConfig: "lazy:faker_counter",
    FakerHashPlaceholderConfig: "lazy:faker_hash",
    FakerPlaceholderConfig: "lazy:faker",
}


def _resolve_lazy_placeholder(key: str) -> type:
    if key == "lazy:faker":
        from piighost.ph_factory.faker import FakerPlaceholderFactory
        return FakerPlaceholderFactory
    if key == "lazy:faker_counter":
        from piighost.ph_factory.faker import FakerCounterPlaceholderFactory
        return FakerCounterPlaceholderFactory
    if key == "lazy:faker_hash":
        from piighost.ph_factory.faker_hash import FakerHashPlaceholderFactory
        return FakerHashPlaceholderFactory
    raise KeyError(key)


def build_placeholder_factory(cfg: BaseModel) -> "AnyPlaceholderFactory":
    builder = _PLACEHOLDER_BUILDERS[type(cfg)]
    cls = builder if not isinstance(builder, str) else _resolve_lazy_placeholder(builder)
    return cls.from_config(cfg)


def build_anonymizer(cfg: DefaultAnonymizerConfig) -> Anonymizer:
    return Anonymizer.from_config(cfg)
```

- [ ] **Step 4: Run all config tests**

Run: `uv run pytest tests/config/ -v`
Expected: All PASS. The previously skipped tests (`test_anonymizer_from_config_default`, `test_chunked_detector_from_config_wraps_inner_regex`) can now be un-skipped — remove the `@pytest.mark.skip` decorators and re-run:

Run: `uv run pytest tests/config/ -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/piighost/config/builders.py tests/config/
git commit -m "feat(config): add builder dispatch tables"
```

---

### Task 13: TOML loader and `build_pipeline`

**Files:**
- Create: `src/piighost/config/loader.py`
- Create: `tests/config/fixtures/minimal.toml`
- Create: `tests/config/fixtures/multi_detector.toml`
- Create: `tests/config/test_loader.py`

- [ ] **Step 1: Write the failing test**

Create `tests/config/fixtures/minimal.toml`:

```toml
[[detectors]]
type = "regex"
patterns = { EMAIL = "[a-z]+@[a-z]+\\.[a-z]+" }
```

Create `tests/config/fixtures/multi_detector.toml`:

```toml
[pipeline]
name = "demo"

[[detectors]]
name = "common"
type = "regex"
patterns = { EMAIL = "[a-z]+@[a-z]+\\.[a-z]+" }

[[detectors]]
name = "secondary"
type = "regex"
patterns = { IP_V4 = "\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b" }
```

Create `tests/config/test_loader.py`:

```python
from pathlib import Path

import pytest

from piighost.config.errors import ConfigError
from piighost.config.loader import build_pipeline, load_config, load_pipeline
from piighost.config.models.pipeline import PipelineConfig
from piighost.detector.base import CompositeDetector, RegexDetector
from piighost.pipeline.thread import ThreadAnonymizationPipeline

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_config_returns_pipeline_config():
    cfg = load_config(FIXTURES / "minimal.toml")
    assert isinstance(cfg, PipelineConfig)
    assert len(cfg.detectors) == 1


def test_load_config_raises_config_error_on_missing_file():
    with pytest.raises(ConfigError):
        load_config(FIXTURES / "does_not_exist.toml")


def test_build_pipeline_returns_pipeline_and_manifest():
    cfg = load_config(FIXTURES / "minimal.toml")
    pipeline, manifest = build_pipeline(cfg)
    assert isinstance(pipeline, ThreadAnonymizationPipeline)
    assert manifest.name is None
    assert manifest.schema_version == 1
    assert len(manifest.detectors) == 1
    assert manifest.detectors[0].type == "regex"
    assert manifest.detectors[0].labels == ["EMAIL"]


def test_build_pipeline_creates_composite_for_multiple_detectors():
    cfg = load_config(FIXTURES / "multi_detector.toml")
    pipeline, manifest = build_pipeline(cfg)
    assert isinstance(pipeline._detector, CompositeDetector)
    assert len(pipeline._detector.detectors) == 2
    assert manifest.name == "demo"
    assert [d.name for d in manifest.detectors] == ["common", "secondary"]


def test_build_pipeline_single_detector_is_unwrapped():
    cfg = load_config(FIXTURES / "minimal.toml")
    pipeline, _ = build_pipeline(cfg)
    assert isinstance(pipeline._detector, RegexDetector)


def test_load_pipeline_combines_load_and_build():
    pipeline, manifest = load_pipeline(FIXTURES / "minimal.toml")
    assert isinstance(pipeline, ThreadAnonymizationPipeline)
    assert manifest.schema_version == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/config/test_loader.py -v`
Expected: FAIL on `ModuleNotFoundError` for `piighost.config.loader`.

- [ ] **Step 3: Implement loader.py**

Create `src/piighost/config/loader.py`:

```python
"""TOML loader for piighost pipelines."""

import sys
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from piighost.anonymizer import Anonymizer
from piighost.config.builders import (
    build_anonymizer,
    build_detector,
    build_entity_linker,
    build_entity_resolver,
    build_placeholder_factory,
    build_span_resolver,
)
from piighost.config.errors import ConfigError
from piighost.config.models.pipeline import PipelineConfig
from piighost.detector.base import (
    AnyDetector,
    ChunkedDetector,
    CompositeDetector,
    RegexDetector,
)
from piighost.pipeline.thread import ThreadAnonymizationPipeline

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # pyrefly: ignore[missing-import]


@dataclass(frozen=True)
class DetectorManifest:
    """Public-facing description of one declared detector."""

    name: str | None
    type: str
    labels: list[str]


@dataclass(frozen=True)
class PipelineManifest:
    """Public-facing description of the loaded pipeline.

    Source of truth for ``/v1/labels`` in ``piighost-api`` and for any
    other introspection consumer.
    """

    name: str | None
    schema_version: int
    detectors: list[DetectorManifest]
    placeholder_factory_type: str


def load_config(path: str | Path) -> PipelineConfig:
    """Parse and validate a TOML file. Does not instantiate components.

    Raises:
        ConfigError: If the file is missing, cannot be parsed, or fails
            validation against :class:`PipelineConfig`.
    """
    path = Path(path)
    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise ConfigError(f"cannot read configuration file {path}: {exc}") from exc

    try:
        data = tomllib.loads(raw_bytes.decode("utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML syntax in {path}: {exc}") from exc

    try:
        return PipelineConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError.from_pydantic(exc, path) from exc


def build_pipeline(
    cfg: PipelineConfig,
) -> tuple[ThreadAnonymizationPipeline, PipelineManifest]:
    """Instantiate components and return the pipeline + manifest."""

    detectors_instances: list[AnyDetector] = [
        build_detector(d_cfg) for d_cfg in cfg.detectors
    ]
    detector: AnyDetector = (
        detectors_instances[0]
        if len(detectors_instances) == 1
        else CompositeDetector(detectors=detectors_instances)
    )

    span_resolver = build_span_resolver(cfg.span_resolver)
    entity_linker = build_entity_linker(cfg.entity_linker)
    entity_resolver = build_entity_resolver(cfg.entity_resolver)
    anonymizer: Anonymizer = build_anonymizer(cfg.anonymizer)

    pipeline = ThreadAnonymizationPipeline(
        detector=detector,
        span_resolver=span_resolver,
        entity_linker=entity_linker,
        entity_resolver=entity_resolver,
        anonymizer=anonymizer,
    )

    manifest = PipelineManifest(
        name=cfg.pipeline.name,
        schema_version=cfg.pipeline.schema_version,
        detectors=[
            DetectorManifest(
                name=d_cfg.name,
                type=d_cfg.type,
                labels=_detector_labels(d_inst),
            )
            for d_cfg, d_inst in zip(cfg.detectors, detectors_instances, strict=True)
        ],
        placeholder_factory_type=cfg.anonymizer.placeholder_factory.type,
    )
    return pipeline, manifest


def load_pipeline(
    path: str | Path,
) -> tuple[ThreadAnonymizationPipeline, PipelineManifest]:
    """Convenience: :func:`load_config` then :func:`build_pipeline`."""
    return build_pipeline(load_config(path))


def _detector_labels(d: AnyDetector) -> list[str]:
    """Return the labels a detector instance can emit, sorted."""
    if isinstance(d, RegexDetector):
        return sorted(d.patterns.keys())
    if isinstance(d, ChunkedDetector):
        return _detector_labels(d.inner)
    labels = getattr(d, "labels", None)
    if labels is None:
        # BaseNERDetector keeps external labels via the property.
        labels = getattr(d, "external_labels", None)
    if labels is None:
        return []
    return sorted(labels)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/config/test_loader.py -v`
Expected: PASS, 6 tests.

- [ ] **Step 5: Commit**

```bash
git add src/piighost/config/loader.py tests/config/fixtures/ tests/config/test_loader.py
git commit -m "feat(config): add TOML loader, build_pipeline, and PipelineManifest"
```

---

### Task 14: Validation error fixtures and tests

**Files:**
- Create: `tests/config/fixtures/invalid/unknown_key.toml`
- Create: `tests/config/fixtures/invalid/bad_threshold.toml`
- Create: `tests/config/fixtures/invalid/bad_regex.toml`
- Create: `tests/config/fixtures/invalid/empty_detectors.toml`
- Modify: `tests/config/test_loader.py`

- [ ] **Step 1: Create invalid fixtures**

Create `tests/config/fixtures/invalid/unknown_key.toml`:

```toml
[[detectors]]
type = "regex"
patterns = { EMAIL = "[a-z]+@[a-z]+" }
rogue_key = "should_be_rejected"
```

Create `tests/config/fixtures/invalid/bad_threshold.toml`:

```toml
[[detectors]]
type = "gliner2"
model = "fake/model"
threshold = 1.5
labels = ["person"]
```

Create `tests/config/fixtures/invalid/bad_regex.toml`:

```toml
[[detectors]]
type = "regex"
patterns = { EMAIL = "((unclosed" }
```

Create `tests/config/fixtures/invalid/empty_detectors.toml`:

```toml
detectors = []
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/config/test_loader.py`:

```python
INVALID = FIXTURES / "invalid"


def test_unknown_key_is_rejected():
    with pytest.raises(ConfigError) as exc:
        load_config(INVALID / "unknown_key.toml")
    assert "rogue_key" in str(exc.value)


def test_bad_threshold_is_rejected():
    with pytest.raises(ConfigError) as exc:
        load_config(INVALID / "bad_threshold.toml")
    assert "threshold" in str(exc.value)


def test_empty_detectors_is_rejected():
    with pytest.raises(ConfigError) as exc:
        load_config(INVALID / "empty_detectors.toml")
    assert "detectors" in str(exc.value)


def test_bad_regex_pattern_raises_config_error_at_build():
    cfg = load_config(INVALID / "bad_regex.toml")  # passes load_config
    with pytest.raises(ConfigError) as exc:
        build_pipeline(cfg)
    assert "EMAIL" in str(exc.value) or "regex" in str(exc.value).lower()
```

- [ ] **Step 3: Run test, expect partial failure**

Run: `uv run pytest tests/config/test_loader.py::test_bad_regex_pattern_raises_config_error_at_build -v`
Expected: FAIL — `RegexDetector.__init__` currently raises `re.error`, not `ConfigError`.

The other invalid tests should already pass thanks to Pydantic.

- [ ] **Step 4: Translate `re.error` into `ConfigError` at build time**

Edit `src/piighost/config/loader.py`. Wrap the `build_detector` calls in `build_pipeline` to catch `re.error`:

```python
import re

# ... inside build_pipeline, replace the list comprehension with:
detectors_instances: list[AnyDetector] = []
for idx, d_cfg in enumerate(cfg.detectors):
    try:
        detectors_instances.append(build_detector(d_cfg))
    except re.error as exc:
        raise ConfigError(
            f"invalid regex in detectors[{idx}] ({d_cfg.name or d_cfg.type}): {exc}"
        ) from exc
```

- [ ] **Step 5: Run tests to verify**

Run: `uv run pytest tests/config/test_loader.py -v`
Expected: All 10 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/config/fixtures/invalid/ tests/config/test_loader.py src/piighost/config/loader.py
git commit -m "feat(config): translate regex compilation errors into ConfigError"
```

---

### Task 15: JSON Schema export

**Files:**
- Modify: `src/piighost/config/loader.py`
- Modify: `src/piighost/config/__init__.py`
- Create: `tests/config/test_schema.py`

- [ ] **Step 1: Write the failing test**

Create `tests/config/test_schema.py`:

```python
from piighost.config import export_schema


def test_export_schema_returns_a_dict():
    schema = export_schema()
    assert isinstance(schema, dict)


def test_export_schema_has_top_level_properties():
    schema = export_schema()
    assert "properties" in schema
    assert "detectors" in schema["properties"]
    assert "anonymizer" in schema["properties"]


def test_export_schema_contains_all_detector_discriminator_tags():
    schema = export_schema()
    # The schema serialization is non-trivial. We assert that every concrete
    # detector type appears somewhere in the rendered JSON Schema.
    import json
    blob = json.dumps(schema)
    for type_name in (
        "regex", "gliner2", "spacy", "transformers", "llm", "chunked",
    ):
        assert f'"const": "{type_name}"' in blob or f'"{type_name}"' in blob


def test_export_schema_contains_all_placeholder_discriminator_tags():
    import json
    blob = json.dumps(export_schema())
    for type_name in (
        "label_counter", "label_hash", "label", "mask",
        "redact_counter", "redact_hash", "redact",
        "faker_counter", "faker_hash", "faker",
    ):
        assert f'"const": "{type_name}"' in blob or f'"{type_name}"' in blob
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/config/test_schema.py -v`
Expected: FAIL — `export_schema` is not in `piighost.config`.

- [ ] **Step 3: Implement `export_schema` and update public API**

Append to `src/piighost/config/loader.py`:

```python
def export_schema() -> dict:
    """Return the JSON Schema of :class:`PipelineConfig`.

    Used by ``piighost schema`` and by future configuration UIs.
    """
    return PipelineConfig.model_json_schema()
```

Update `src/piighost/config/__init__.py`:

```python
"""Declarative TOML configuration for piighost pipelines."""

from piighost.config.errors import ConfigError
from piighost.config.loader import (
    DetectorManifest,
    PipelineManifest,
    build_pipeline,
    export_schema,
    load_config,
    load_pipeline,
)
from piighost.config.models.pipeline import PipelineConfig

__all__ = [
    "ConfigError",
    "DetectorManifest",
    "PipelineConfig",
    "PipelineManifest",
    "build_pipeline",
    "export_schema",
    "load_config",
    "load_pipeline",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/config/test_schema.py -v`
Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
git add src/piighost/config/__init__.py src/piighost/config/loader.py tests/config/test_schema.py
git commit -m "feat(config): export JSON Schema of PipelineConfig"
```

---

## Phase 5: CLI

### Task 16: `piighost validate` and `piighost schema` commands

**Files:**
- Create: `src/piighost/cli/__init__.py`
- Modify: `pyproject.toml` (add `[project.scripts]` entry)
- Create: `tests/cli/__init__.py`
- Create: `tests/cli/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/cli/__init__.py` (empty).

Create `tests/cli/test_cli.py`:

```python
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from piighost.cli import app

runner = CliRunner()
FIXTURES = Path(__file__).parent.parent / "config" / "fixtures"


def test_validate_succeeds_on_minimal_toml():
    result = runner.invoke(app, ["validate", str(FIXTURES / "minimal.toml")])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output


def test_validate_fails_on_unknown_key():
    result = runner.invoke(
        app, ["validate", str(FIXTURES / "invalid" / "unknown_key.toml")]
    )
    assert result.exit_code == 1
    assert "rogue_key" in result.output


def test_validate_fails_on_missing_file():
    result = runner.invoke(app, ["validate", "/tmp/no_such_file_xyz.toml"])
    assert result.exit_code == 1


def test_schema_outputs_valid_json():
    result = runner.invoke(app, ["schema"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert "properties" in parsed
    assert "detectors" in parsed["properties"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_cli.py -v`
Expected: FAIL on `ModuleNotFoundError` for `piighost.cli`.

- [ ] **Step 3: Implement the CLI**

Create `src/piighost/cli/__init__.py`:

```python
"""``piighost`` command-line interface.

Subcommands:

* ``validate <file.toml>`` parses and validates a pipeline configuration
  without instantiating components. Exit code 0 on success, 1 on error.
* ``schema`` prints the JSON Schema of :class:`PipelineConfig` to stdout.

The CLI requires the ``config`` optional dependency group. A friendly
error explains how to install it if Typer is missing.
"""

import json
import sys
from pathlib import Path

import typer

from piighost.config import ConfigError, export_schema, load_config

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def validate(
    path: Path = typer.Argument(..., exists=False, help="Path to a TOML pipeline config."),
) -> None:
    """Validate a piighost pipeline TOML configuration."""
    try:
        load_config(path)
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)
    typer.echo(f"OK: {path}")


@app.command()
def schema() -> None:
    """Print the JSON Schema of PipelineConfig to stdout."""
    typer.echo(json.dumps(export_schema(), indent=2, ensure_ascii=False))


def main() -> None:
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/cli/test_cli.py -v`
Expected: PASS, 4 tests.

- [ ] **Step 5: Register the entry point in `pyproject.toml`**

Add to `pyproject.toml` (right after the existing `[project.urls]` block, before `[project.optional-dependencies]`):

```toml
[project.scripts]
piighost = "piighost.cli:main"
```

Re-sync and verify:

Run: `uv sync --group dev --group config`
Run: `uv run piighost --help`
Expected: Help screen with `validate` and `schema` subcommands.

- [ ] **Step 6: Commit**

```bash
git add src/piighost/cli/ tests/cli/ pyproject.toml uv.lock
git commit -m "feat(cli): add piighost validate and piighost schema commands"
```

---

## Phase 6: Documentation

### Task 17: TOML configuration reference (English)

**Files:**
- Create: `docs/en/configuration/toml.md`
- Modify: `docs/en/index.md` (or the existing nav file) to link the new page

- [ ] **Step 1: Inspect existing docs structure**

Run: `ls docs/en/`
Read whatever navigation file the project uses (likely `zensical.toml` or `mkdocs.yml`) to know where to register the new page.

- [ ] **Step 2: Write the reference page**

Create `docs/en/configuration/toml.md`:

```markdown
# TOML pipeline configuration

`piighost` accepts a declarative TOML file that fully describes a
`ThreadAnonymizationPipeline`. The file is consumed by:

- The `piighost-api` server (`piighost-api serve --config <file>`).
- The `piighost validate` and `piighost schema` CLI commands.
- Any application that imports `piighost.config.load_pipeline`.

No Python code runs at load time. The format is fully validated by
Pydantic v2; unknown keys raise an error rather than being silently
ignored.

## Minimal example

```toml
[[detectors]]
type = "regex"
patterns = { EMAIL = "[a-zA-Z0-9._%+\\-]+@[a-zA-Z0-9.\\-]+\\.[a-zA-Z]{2,}" }
```

This produces a pipeline with one regex detector, default span and
entity resolvers, and the `label_counter` placeholder factory
(yielding tokens like `<<EMAIL_1>>`).

## Full example

```toml
[pipeline]
name = "pii-en-multi"
description = "GLiNER2 + regex coverage for English text"
schema_version = 1

[[detectors]]
name = "common"
type = "regex"
patterns = { EMAIL = "[a-z]+@[a-z]+\\.[a-z]+", IP_V4 = "\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b" }

[[detectors]]
name = "gliner2"
type = "gliner2"
model = "fastino/gliner2-multi-v1"
threshold = 0.5
labels = ["person", "city", "email address"]

[span_resolver]
type = "confidence"

[entity_linker]
type = "exact"

[entity_resolver]
type = "merge"

[anonymizer.placeholder_factory]
type = "label_counter"
```

## Reference

### `[pipeline]` (optional)

| Key              | Type    | Default | Meaning                          |
| ---------------- | ------- | ------- | -------------------------------- |
| `name`           | string  | `null`  | Exposed by `/v1/labels`.         |
| `description`    | string  | `null`  | Free-text doc, not used by code. |
| `schema_version` | integer | `1`     | Currently the only valid value.  |

### `[[detectors]]` (required, at least one)

Each entry declares one detector. Multiple entries form an implicit
`CompositeDetector`, in order.

Common keys:

| Key    | Type    | Required | Meaning                                       |
| ------ | ------- | -------- | --------------------------------------------- |
| `type` | string  | yes      | Discriminator (`regex`, `gliner2`, ...).       |
| `name` | string  | no       | Used for `/v1/labels` grouping.               |

Per `type`:

**`regex`**

| Key        | Type             | Required | Meaning                       |
| ---------- | ---------------- | -------- | ----------------------------- |
| `patterns` | table[str, str]  | yes      | Label name to regex pattern.  |

**`gliner2`** (requires `piighost[gliner2]`)

| Key         | Type     | Required | Meaning                              |
| ----------- | -------- | -------- | ------------------------------------ |
| `model`     | string   | yes      | HF model id, e.g. `fastino/gliner2-multi-v1`. |
| `labels`    | list[str]| yes      | Entity types to look for.            |
| `threshold` | float    | no       | Confidence cutoff, default `0.5`.    |
| `flat_ner`  | bool     | no       | Default `true`.                      |

**`spacy`** (requires `piighost[spacy]`)

| Key      | Type     | Required | Meaning                          |
| -------- | -------- | -------- | -------------------------------- |
| `model`  | string   | yes      | spaCy model name.                |
| `labels` | list[str]| yes      | spaCy entity types to keep.      |

**`transformers`** (requires `piighost[transformers]`)

| Key         | Type   | Required | Meaning                              |
| ----------- | ------ | -------- | ------------------------------------ |
| `model`     | string | yes      | HF model id.                         |
| `threshold` | float  | no       | Confidence cutoff, default `0.5`.    |

**`llm`** (requires `piighost[llm]`, secrets in env)

| Key        | Type     | Required | Meaning                              |
| ---------- | -------- | -------- | ------------------------------------ |
| `provider` | string   | yes      | e.g. `openai`, `anthropic`.          |
| `model`    | string   | yes      | Provider-specific model id.          |
| `labels`   | list[str]| yes      | Labels to extract.                   |

API keys are never stored in TOML. They are read from environment
variables by the provider client.

**`chunked`** (wraps another detector)

| Key          | Type           | Required | Meaning                          |
| ------------ | -------------- | -------- | -------------------------------- |
| `chunk_size` | integer (>= 1) | yes      | Character window per chunk.       |
| `overlap`    | integer (>= 0) | no       | Overlap between chunks, default 0. |
| `inner`      | detector cfg   | yes      | The detector to run on each chunk. |

### `[span_resolver]` (optional, default `confidence`)

| `type`        | Behavior                                                            |
| ------------- | ------------------------------------------------------------------- |
| `confidence`  | Keep the highest-confidence detection when spans overlap.            |
| `disabled`    | No conflict resolution.                                              |

### `[entity_linker]` (optional, default `exact`)

| `type`     | Behavior                                                  |
| ---------- | --------------------------------------------------------- |
| `exact`    | Word-boundary regex links repeated mentions.              |
| `disabled` | No cross-mention linking.                                 |

### `[entity_resolver]` (optional, default `merge`)

| `type`     | Behavior                                                  | Extra key |
| ---------- | --------------------------------------------------------- | --------- |
| `merge`    | Union-find merge.                                         |           |
| `fuzzy`    | Jaro-Winkler merge.                                       | `threshold` (float, 0.0..1.0, default `0.85`). |
| `disabled` | No entity merging.                                        |           |

### `[anonymizer]` (optional, default `default`)

```toml
[anonymizer]
type = "default"

[anonymizer.placeholder_factory]
type = "label_counter"     # see below
```

### `[anonymizer.placeholder_factory]` (optional, default `label_counter`)

| `type`            | Token format                       | Extra keys                  |
| ----------------- | ---------------------------------- | --------------------------- |
| `label_counter`   | `<<PERSON_1>>`                     |                             |
| `label_hash`      | `<<PERSON_a1b2c3>>`                | `hash_length` (4..64, default 8) |
| `label`           | `<<PERSON>>` (no disambiguation)   |                             |
| `mask`            | `*****`                            | `mask_char` (1 char, default `*`) |
| `redact_counter`  | `<<REDACTED_1>>`                   |                             |
| `redact_hash`     | `<<REDACTED_a1b2c3>>`              | `hash_length`               |
| `redact`          | `<<REDACTED>>`                     |                             |
| `faker_counter`   | Realistic synthetic value, indexed | `locale` (default `en_US`)  |
| `faker_hash`      | Realistic synthetic value, hashed  | `locale`, `hash_length`     |
| `faker`           | Realistic synthetic value          | `locale`                    |

Faker-based factories require `piighost[faker]`.

## CLI helpers

```
$ piighost validate ./pipeline.toml
OK: pipeline.toml

$ piighost schema > schema.json
```

`schema.json` is the canonical JSON Schema describing the structure
above, suitable for editor autocompletion or any future web UI.
```

- [ ] **Step 3: Register the page in the docs nav**

Open whichever file (zensical config, mkdocs.yml, etc.) controls the nav. Add an entry for `Configuration → TOML reference → configuration/toml.md` (or equivalent based on the project's existing nav style). If the file is YAML/TOML, follow surrounding indentation; if the doc engine auto-discovers files in the directory, this step is a no-op.

- [ ] **Step 4: Verify the page renders**

Run the project's docs preview command if one exists (likely `make docs` or `zensical serve`). Browse to the new page and confirm it renders.

- [ ] **Step 5: Commit**

```bash
git add docs/en/configuration/toml.md docs/en/  # also stage nav file if changed
git commit -m "docs(en): add TOML pipeline configuration reference"
```

---

### Task 18: TOML configuration reference (French)

**Files:**
- Create: `docs/fr/configuration/toml.md`
- Modify: French nav file

- [ ] **Step 1: Translate the English reference**

Translate the English page from Task 17 into French. Keep all code blocks, table key names, and TOML examples identical (code is in English; only prose is translated).

Create `docs/fr/configuration/toml.md` with the French translation, mirroring the structure of `docs/en/configuration/toml.md` section by section. Avoid em dashes (use colons, commas, or periods); avoid mid-sentence colons where a period works (this is project house style).

- [ ] **Step 2: Register the page in the French nav**

Same operation as Task 17 step 3, on the French side.

- [ ] **Step 3: Commit**

```bash
git add docs/fr/configuration/toml.md docs/fr/
git commit -m "docs(fr): add TOML pipeline configuration reference"
```

---

## Final checks

### Task 19: Whole-suite check, lint, type-check

- [ ] **Step 1: Full test run**

Run: `uv run pytest -v`
Expected: All tests PASS. No regressions in pre-existing tests.

- [ ] **Step 2: Integration tests (optional, slow)**

If GLiNER2 / spaCy / transformers are installed locally:

Run: `uv run pytest -v -m integration`
Expected: PASS.

- [ ] **Step 3: Lint and type-check**

Run: `make lint`
Expected: No errors from ruff or pyrefly.

Fix any issue inline. Do NOT skip with `# noqa` or `# pyrefly: ignore` unless the underlying cause is genuinely outside this PR's scope.

- [ ] **Step 4: Verify the public API surface**

Run: `uv run python -c "from piighost.config import ConfigError, PipelineConfig, PipelineManifest, build_pipeline, export_schema, load_config, load_pipeline; print('OK')"`
Expected: `OK`.

Run: `uv run piighost --help`
Expected: Shows `validate` and `schema` subcommands.

Run: `uv run piighost schema | head -5`
Expected: JSON output starting with `{`.

- [ ] **Step 5: Final commit (if anything changed during cleanup)**

If lint produced reformat changes:

```bash
git add -p
git commit -m "style: ruff format pass"
```

Otherwise nothing to commit.

---

## Self-review checklist (executor reads before declaring done)

- [ ] Every task has at least one failing-test step before any implementation.
- [ ] No `pytest.mark.skip` left in the suite once Phase 4 is complete.
- [ ] `piighost validate <file>` exits 0 on `minimal.toml` and exits 1 on every invalid fixture.
- [ ] `piighost schema | jq .` parses and contains all detector + placeholder discriminator tags.
- [ ] `pyproject.toml` lists `config` in both `[project.optional-dependencies]` and `[dependency-groups]`.
- [ ] `piighost = "piighost.cli:main"` is registered in `[project.scripts]`.
- [ ] The English and French docs pages exist and are reachable from each side's nav.
- [ ] No `from_config` references a builder that does not exist.
- [ ] `pyrefly` reports zero errors on the new sub-packages.
