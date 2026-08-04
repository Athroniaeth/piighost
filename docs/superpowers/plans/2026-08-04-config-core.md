# Config Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the config composition-root core: a `config/` package (behind the `config` extra) that loads a TOML via pydantic-settings, validates discriminated-union models each carrying a `build()`, and assembles a working `AnonymizationPipeline`.

**Architecture:** Per-component pydantic models under `config/models/`, discriminated on `type`, each with a `build()` that imports and constructs its core component (one-way config->core coupling, no builder registry). `PipelineConfig(BaseSettings)` layers init > env > TOML file, and `load_pipeline(path)` returns `PipelineConfig(...).build()`.

**Tech Stack:** Python 3.11+, pydantic + pydantic-settings (extra `config`), tomllib (stdlib), pytest.

---

## Conventions for every task

- Run tests with `uv run --no-sync`. Before each pytest run clear bytecode: `find src tests -name __pycache__ -type d -exec rm -rf {} +`.
- Python 3.11+ native typing, NO `from __future__ import annotations`. Docstrings plain prose plus bullet lists only, no markdown/RST. English only. Conventional Commits. ANN enforced on tests.
- pydantic is in the dev venv; Task 1 adds `pydantic-settings` to the `config` extra and the dev group, then `uv sync`. After that, the config tests run for real.
- `config/` imports pydantic (an extra), so `config/__init__.py` guards `find_spec("pydantic_settings")` and raises `ImportError` naming `piighost[config]`. The core never imports `config` (guarded by the existing `test_core_no_extras.py`). No pyrefly suppression is expected; report if pyrefly complains rather than suppressing.
- `build()` methods return the port type of their component, parameterized where generic: placeholder factories return `AnyPlaceholderFactory[PlaceholderPreservation]` (covariant, so a concrete factory's narrower tag fits), the anonymizer returns `AnyAnonymizer[PlaceholderPreservation]`, the pipeline `AnonymizationPipeline[PlaceholderPreservation]`. The config path erases the precise phantom tag to the base, expected for a runtime-built pipeline.

## File structure

- Modify `pyproject.toml` — add `pydantic-settings` to the `config` extra (both blocks) and the dev group (Task 1).
- Modify `src/piighost/exceptions.py` — `ConfigError`, `ConfigFileError`, `ConfigValidationError` (Task 1).
- Create `src/piighost/config/models/{__init__,common,placeholder,detector,linker,anonymizer}.py` (Task 1).
- Create `src/piighost/config/settings.py` — `PipelineConfig`, `load_config`, `load_pipeline` (Task 2).
- Create `src/piighost/config/errors.py` — re-export the config exceptions (Task 2).
- Create `src/piighost/config/__init__.py` — guard + public exports (Task 2).
- Modify `tests/regression/test_imports.py` — the three exceptions (Task 3).
- Tests: `tests/config/test_models.py` (Task 1), `tests/config/test_settings.py` (Task 2).

---

### Task 1: Config models with build(), packaging, exceptions

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/piighost/exceptions.py`
- Create: `src/piighost/config/models/__init__.py`
- Create: `src/piighost/config/models/common.py`
- Create: `src/piighost/config/models/placeholder.py`
- Create: `src/piighost/config/models/detector.py`
- Create: `src/piighost/config/models/linker.py`
- Create: `src/piighost/config/models/anonymizer.py`
- Test: `tests/config/test_models.py`

- [ ] **Step 1: Add packaging and sync**

In `pyproject.toml`, in the `[project.optional-dependencies]` `config` block, add `pydantic-settings>=2.0`:

```toml
config = [
    "pydantic>=2.6",
    "pydantic-settings>=2.0",
    "typer>=0.12",
    "tomli>=2.0; python_version < '3.11'",
]
```

Mirror the same addition in the `[dependency-groups]` `config` block. In the `dev` group, add the line `"pydantic-settings>=2.0",` (pydantic is already there).

Run: `uv sync`
Verify: `uv run --no-sync python -c "import pydantic_settings; print('ok')"` prints `ok`.

- [ ] **Step 2: Write the failing model tests**

Create `tests/config/test_models.py`:

```python
"""Tests for the config component models and their build()."""

import pytest
from pydantic import ValidationError

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import CompositeDetector, RegexDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import (
    LabelCounterPlaceholderFactory,
    LabelPlaceholderFactory,
    MaskPlaceholderFactory,
    RedactPlaceholderFactory,
)
from piighost.config.models.anonymizer import AnonymizerConfig
from piighost.config.models.detector import (
    CompositeDetectorConfig,
    DetectorConfig,
    RegexDetectorConfig,
)
from piighost.config.models.linker import ExactLinkerConfig
from piighost.config.models.placeholder import (
    LabelCounterPlaceholderConfig,
    LabelPlaceholderConfig,
    MaskPlaceholderConfig,
    RedactPlaceholderConfig,
)
from piighost.models import Detection, Entity, Span


def _entity(text: str = "Emma", label: str = "PERSON") -> Entity:
    """Build a one-detection entity for a value and label."""
    detection = Detection(span=Span(0, len(text)), text=text, label=label, confidence=1.0)
    return Entity((detection,))


class TestDetectorConfig:
    def test_regex_builds_a_regex_detector(self) -> None:
        """A regex config builds a RegexDetector over its patterns."""
        config = RegexDetectorConfig(type="regex", patterns={"EMAIL": "a@b"})
        detector = config.build()
        assert isinstance(detector, RegexDetector)
        assert detector.patterns == {"EMAIL": "a@b"}

    def test_composite_builds_from_nested_detectors(self) -> None:
        """A composite config builds a CompositeDetector from its children."""
        config = CompositeDetectorConfig(
            type="composite",
            detectors=[RegexDetectorConfig(type="regex", patterns={"A": "a"})],
        )
        detector = config.build()
        assert isinstance(detector, CompositeDetector)

    def test_unknown_key_is_rejected(self) -> None:
        """A model forbids keys it does not declare, catching typos."""
        with pytest.raises(ValidationError):
            RegexDetectorConfig(type="regex", patterns={"A": "a"}, nope=1)


class TestPlaceholderConfig:
    async def test_each_factory_builds_and_renders(self) -> None:
        """Each core factory config builds a factory rendering its token."""
        entities = [_entity()]
        redact = RedactPlaceholderConfig(type="redact").build()
        label = LabelPlaceholderConfig(type="label").build()
        counter = LabelCounterPlaceholderConfig(type="label_counter").build()
        mask = MaskPlaceholderConfig(type="mask").build()
        assert isinstance(redact, RedactPlaceholderFactory)
        assert isinstance(label, LabelPlaceholderFactory)
        assert isinstance(counter, LabelCounterPlaceholderFactory)
        assert isinstance(mask, MaskPlaceholderFactory)
        assert redact.create(entities)[entities[0]] == "<<REDACT>>"
        assert label.create(entities)[entities[0]] == "<<PERSON>>"
        assert counter.create(entities)[entities[0]] == "<<PERSON:1>>"
        assert mask.create(entities)[entities[0]] == "E***"

    def test_mask_carries_its_options(self) -> None:
        """The mask config forwards visible and mask_char to the factory."""
        factory = MaskPlaceholderConfig(type="mask", visible=2, mask_char="#").build()
        entities = [_entity(text="Emma")]
        assert factory.create(entities)[entities[0]] == "Em##"


class TestLinkerAndAnonymizerConfig:
    def test_exact_linker_builds(self) -> None:
        """The linker config builds an ExactEntityLinker."""
        assert isinstance(ExactLinkerConfig(type="exact").build(), ExactEntityLinker)

    def test_anonymizer_builds_on_its_placeholder(self) -> None:
        """The anonymizer config builds an Anonymizer on its factory."""
        config = AnonymizerConfig(placeholder=RedactPlaceholderConfig(type="redact"))
        anonymizer = config.build()
        assert isinstance(anonymizer, Anonymizer)
        assert isinstance(anonymizer.factory, RedactPlaceholderFactory)


class TestDiscriminatedUnion:
    def test_type_selects_the_model(self) -> None:
        """The type discriminant parses to the matching concrete model."""
        from pydantic import TypeAdapter

        adapter = TypeAdapter(DetectorConfig)
        parsed = adapter.validate_python({"type": "regex", "patterns": {"A": "a"}})
        assert isinstance(parsed, RegexDetectorConfig)
```

- [ ] **Step 3: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/config/test_models.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'piighost.config'`.

- [ ] **Step 4: Add the exceptions and the models**

In `src/piighost/exceptions.py`, at the end, add:

```python
class ConfigError(PIIGhostError):
    """Base class for errors raised while loading a configuration.

    Catch this to handle any configuration failure at once, or catch one of its
    subclasses to react to a specific violation.
    """


class ConfigFileError(ConfigError):
    """Raised when a configuration file cannot be read or parsed.

    The file is missing, unreadable, or not valid TOML.
    """


class ConfigValidationError(ConfigError):
    """Raised when a configuration parses but fails schema validation.

    It wraps pydantic's ValidationError in the library's error family, so a
    caller catches ConfigError rather than a pydantic type.
    """
```

Create `src/piighost/config/models/__init__.py`:

```python
"""Configuration models: one discriminated-union model family per component.

Each model carries a build() that constructs its core component, so the
composition root is the config models themselves, not a separate builder
registry.
"""
```

Create `src/piighost/config/models/common.py`:

```python
"""Shared base for the component configuration models."""

from pydantic import BaseModel, ConfigDict


class _ComponentConfig(BaseModel):
    """Base for a component's configuration model.

    Forbids keys the model does not declare, so a typo in a TOML table fails
    validation instead of being silently ignored.
    """

    model_config = ConfigDict(extra="forbid")
```

Create `src/piighost/config/models/placeholder.py`:

```python
"""Placeholder factory configuration models, discriminated on type."""

from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.components.placeholder import (
    LabelCounterPlaceholderFactory,
    LabelPlaceholderFactory,
    MaskPlaceholderFactory,
    RedactPlaceholderFactory,
)
from piighost.components.placeholder.base import AnyPlaceholderFactory
from piighost.components.placeholder.tags import PlaceholderPreservation
from piighost.config.models.common import _ComponentConfig


class RedactPlaceholderConfig(_ComponentConfig):
    """Config for the redact factory, one constant token for every entity."""

    type: Literal["redact"]

    def build(self) -> AnyPlaceholderFactory[PlaceholderPreservation]:
        """Build the redact placeholder factory."""
        return RedactPlaceholderFactory()


class LabelPlaceholderConfig(_ComponentConfig):
    """Config for the label factory, one token per label."""

    type: Literal["label"]

    def build(self) -> AnyPlaceholderFactory[PlaceholderPreservation]:
        """Build the label placeholder factory."""
        return LabelPlaceholderFactory()


class LabelCounterPlaceholderConfig(_ComponentConfig):
    """Config for the label-counter factory, a numbered token per label."""

    type: Literal["label_counter"]

    def build(self) -> AnyPlaceholderFactory[PlaceholderPreservation]:
        """Build the label-counter placeholder factory."""
        return LabelCounterPlaceholderFactory()


class MaskPlaceholderConfig(_ComponentConfig):
    """Config for the mask factory, keeping a few leading characters."""

    type: Literal["mask"]
    visible: int = Field(default=1, ge=0)
    mask_char: str = Field(default="*", min_length=1, max_length=1)

    def build(self) -> AnyPlaceholderFactory[PlaceholderPreservation]:
        """Build the mask placeholder factory with its visible count and char."""
        return MaskPlaceholderFactory(visible=self.visible, mask_char=self.mask_char)


PlaceholderConfig = Annotated[
    RedactPlaceholderConfig
    | LabelPlaceholderConfig
    | LabelCounterPlaceholderConfig
    | MaskPlaceholderConfig,
    Discriminator("type"),
]
```

Create `src/piighost/config/models/detector.py`:

```python
"""Detector configuration models, discriminated on type."""

from typing import Annotated, Literal

from pydantic import Discriminator, Field

from piighost.components.detector import CompositeDetector, RegexDetector
from piighost.components.detector.base import AnyDetector
from piighost.config.models.common import _ComponentConfig


class RegexDetectorConfig(_ComponentConfig):
    """Config for the regex detector, one pattern per label."""

    type: Literal["regex"]
    patterns: dict[str, str] = Field(min_length=1)

    def build(self) -> AnyDetector:
        """Build a RegexDetector over the configured patterns."""
        return RegexDetector(self.patterns)


class CompositeDetectorConfig(_ComponentConfig):
    """Config for the composite detector, running child detectors together."""

    type: Literal["composite"]
    detectors: "list[DetectorConfig]" = Field(min_length=1)

    def build(self) -> AnyDetector:
        """Build a CompositeDetector from the built child detectors."""
        children = [detector.build() for detector in self.detectors]
        return CompositeDetector(children)


DetectorConfig = Annotated[
    RegexDetectorConfig | CompositeDetectorConfig,
    Discriminator("type"),
]


CompositeDetectorConfig.model_rebuild()
```

Create `src/piighost/config/models/linker.py`:

```python
"""Entity linker configuration model."""

from typing import Literal

from piighost.components.linker import ExactEntityLinker
from piighost.components.linker.base import AnyEntityLinker
from piighost.config.models.common import _ComponentConfig


class ExactLinkerConfig(_ComponentConfig):
    """Config for the exact entity linker, grouping by casefolded value."""

    type: Literal["exact"]

    def build(self) -> AnyEntityLinker:
        """Build an ExactEntityLinker."""
        return ExactEntityLinker()


LinkerConfig = ExactLinkerConfig
"""The linker configuration.

A plain alias while one linker exists; it becomes a discriminated union when a
second linker lands in the coverage brick.
"""
```

Create `src/piighost/config/models/anonymizer.py`:

```python
"""Anonymizer configuration model."""

from piighost.components.anonymizer import Anonymizer
from piighost.components.anonymizer.base import AnyAnonymizer
from piighost.components.placeholder.tags import PlaceholderPreservation
from piighost.config.models.common import _ComponentConfig
from piighost.config.models.placeholder import PlaceholderConfig


class AnonymizerConfig(_ComponentConfig):
    """Config for the anonymizer, built on a placeholder factory."""

    placeholder: PlaceholderConfig

    def build(self) -> AnyAnonymizer[PlaceholderPreservation]:
        """Build an Anonymizer on the configured placeholder factory."""
        return Anonymizer(self.placeholder.build())
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/config/test_models.py -q`
Expected: PASS, all model tests green.

- [ ] **Step 6: Lint, types, commit**

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean, pyrefly 0 errors.

```bash
git add pyproject.toml uv.lock src/piighost/exceptions.py src/piighost/config/models tests/config/test_models.py
git commit -m "feat(config): add the component config models with build()"
```

---

### Task 2: Settings, loading, and the config package entry

**Files:**
- Create: `src/piighost/config/errors.py`
- Create: `src/piighost/config/settings.py`
- Create: `src/piighost/config/__init__.py`
- Test: `tests/config/test_settings.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/config/test_settings.py`:

```python
"""Tests for loading a pipeline config from TOML via pydantic-settings."""

from pathlib import Path
from typing import Any

import pytest

from piighost.config import PipelineConfig, load_config, load_pipeline
from piighost.exceptions import ConfigFileError, ConfigValidationError

_VALID_TOML = """
name = "from-file"

[detector]
type = "regex"
patterns = { EMAIL = "[a-z]+@[a-z.]+" }

[linker]
type = "exact"

[anonymizer.placeholder]
type = "redact"
"""


def _write(tmp_path: Path, text: str) -> Path:
    """Write text to a config.toml under tmp_path and return the path."""
    path = tmp_path / "config.toml"
    path.write_text(text)
    return path


class TestLoadConfig:
    def test_valid_toml_parses(self, tmp_path: Path) -> None:
        """A valid TOML parses into a PipelineConfig."""
        config = load_config(_write(tmp_path, _VALID_TOML))
        assert isinstance(config, PipelineConfig)
        assert config.name == "from-file"

    def test_missing_file_raises_config_file_error(self, tmp_path: Path) -> None:
        """A missing file raises ConfigFileError."""
        with pytest.raises(ConfigFileError):
            load_config(tmp_path / "absent.toml")

    def test_invalid_toml_raises_config_file_error(self, tmp_path: Path) -> None:
        """Syntactically invalid TOML raises ConfigFileError."""
        with pytest.raises(ConfigFileError):
            load_config(_write(tmp_path, "this is = = not toml"))

    def test_invalid_schema_raises_config_validation_error(
        self, tmp_path: Path
    ) -> None:
        """A detector without a type raises ConfigValidationError."""
        bad = _VALID_TOML.replace('type = "regex"\n', "")
        with pytest.raises(ConfigValidationError):
            load_config(_write(tmp_path, bad))


class TestEnvOverride:
    def test_env_overrides_a_top_level_scalar(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """A PIIGHOST_ env var overrides the file's top-level scalar."""
        monkeypatch.setenv("PIIGHOST_NAME", "from-env")
        config = load_config(_write(tmp_path, _VALID_TOML))
        assert config.name == "from-env"


class TestLoadPipeline:
    async def test_builds_a_working_pipeline(self, tmp_path: Path) -> None:
        """load_pipeline builds a pipeline that anonymizes end to end."""
        pipeline = load_pipeline(_write(tmp_path, _VALID_TOML))
        result = await pipeline.anonymize("reach a@b.co now")
        assert result.text == "reach <<REDACT>> now"

    async def test_composite_detector_from_toml(self, tmp_path: Path) -> None:
        """A composite detector declared in TOML builds and runs."""
        toml = _VALID_TOML.replace(
            '[detector]\ntype = "regex"\npatterns = { EMAIL = "[a-z]+@[a-z.]+" }\n',
            '[detector]\ntype = "composite"\n'
            '[[detector.detectors]]\ntype = "regex"\npatterns = { EMAIL = "[a-z]+@[a-z.]+" }\n',
        )
        pipeline = load_pipeline(_write(tmp_path, toml))
        result = await pipeline.anonymize("reach a@b.co now")
        assert result.text == "reach <<REDACT>> now"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/config/test_settings.py -q`
Expected: FAIL with `ImportError: cannot import name 'load_config' from 'piighost.config'` (or the package missing).

- [ ] **Step 3: Write the errors module, settings, and package entry**

Create `src/piighost/config/errors.py`:

```python
"""Config error family, re-exported from the core exceptions module.

The classes live in piighost.exceptions so a caller can catch them without the
config extra installed; this module re-exports them for config-local imports.
"""

from piighost.exceptions import (
    ConfigError,
    ConfigFileError,
    ConfigValidationError,
)

__all__ = ["ConfigError", "ConfigFileError", "ConfigValidationError"]
```

Create `src/piighost/config/settings.py`:

```python
"""Pipeline configuration settings and the loading entry points.

PipelineConfig is a pydantic-settings model layering, in decreasing precedence,
explicit init arguments, environment variables prefixed PIIGHOST_, then the TOML
file. The file path is injected per call through a context variable read by
settings_customise_sources, so the path is not frozen at class definition.
"""

import tomllib
from contextvars import ContextVar
from pathlib import Path
from typing import ClassVar

from pydantic import ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from piighost.components.placeholder.tags import PlaceholderPreservation
from piighost.config.models.anonymizer import AnonymizerConfig
from piighost.config.models.detector import DetectorConfig
from piighost.config.models.linker import LinkerConfig
from piighost.exceptions import ConfigFileError, ConfigValidationError
from piighost.pipeline import AnonymizationPipeline

_toml_path: ContextVar[Path | None] = ContextVar("_toml_path", default=None)
"""The TOML file the current load reads, set by load_config, read by the source."""


class PipelineConfig(BaseSettings):
    """The whole pipeline configuration, loaded from TOML with env overrides.

    Attributes:
        name: An optional name for the pipeline, a top-level scalar an env var
            can override.
        detector: The detector stage configuration.
        linker: The entity linker configuration.
        anonymizer: The anonymizer configuration.
    """

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="PIIGHOST_", extra="forbid"
    )

    name: str | None = None
    detector: DetectorConfig
    linker: LinkerConfig
    anonymizer: AnonymizerConfig

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Layer init, then env, then the TOML file the current load points at."""
        sources: list[PydanticBaseSettingsSource] = [init_settings, env_settings]
        path = _toml_path.get()
        if path is not None:
            sources.append(TomlConfigSettingsSource(settings_cls, toml_file=path))
        return tuple(sources)

    def build(self) -> AnonymizationPipeline[PlaceholderPreservation]:
        """Assemble the AnonymizationPipeline the configuration describes."""
        detector = self.detector.build()
        linker = self.linker.build()
        anonymizer = self.anonymizer.build()
        return AnonymizationPipeline(detector, linker, anonymizer)


def load_config(path: str | Path) -> PipelineConfig:
    """Parse and validate a TOML file into a PipelineConfig, building nothing.

    Raises:
        ConfigFileError: If the file is missing, unreadable, or invalid TOML.
        ConfigValidationError: If the parsed data fails schema validation.
    """
    resolved = Path(path)
    if not resolved.is_file():
        raise ConfigFileError(f"configuration file not found: {resolved}")

    token = _toml_path.set(resolved)
    try:
        return PipelineConfig()
    except tomllib.TOMLDecodeError as exc:
        raise ConfigFileError(f"invalid TOML in {resolved}: {exc}") from exc
    except ValidationError as exc:
        raise ConfigValidationError(f"invalid configuration in {resolved}: {exc}") from exc
    finally:
        _toml_path.reset(token)


def load_pipeline(path: str | Path) -> AnonymizationPipeline[PlaceholderPreservation]:
    """Load a configuration and build its AnonymizationPipeline."""
    return load_config(path).build()
```

Create `src/piighost/config/__init__.py`:

```python
"""Configuration: build a pipeline from a TOML file.

This package needs the config optional dependencies (pydantic-settings). It is
guarded so importing it without them raises an ImportError pointing at the
extra. The core never imports this package; configuration depends on the core,
not the other way round.
"""

import importlib.util

if importlib.util.find_spec("pydantic_settings") is None:
    raise ImportError(
        "piighost configuration requires the config extra. "
        "Install it with: pip install piighost[config]"
    )

from piighost.config.settings import (  # noqa: E402
    PipelineConfig,
    load_config,
    load_pipeline,
)

__all__ = ["PipelineConfig", "load_config", "load_pipeline"]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/config/ -q`
Expected: PASS (models + settings). If `TomlConfigSettingsSource(settings_cls, toml_file=path)` does not accept `toml_file`, consult the installed pydantic-settings version and pass the path via its documented parameter, keeping the per-call ContextVar approach; report if the API differs.

- [ ] **Step 5: Run the full suite, lint, types**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest -q`
Expected: PASS, including the existing `test_core_no_extras.py` (the core still imports no config).

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean, pyrefly 0 errors.

- [ ] **Step 6: Commit**

```bash
git add src/piighost/config/errors.py src/piighost/config/settings.py src/piighost/config/__init__.py tests/config/test_settings.py
git commit -m "feat(config): load a pipeline from TOML with pydantic-settings"
```

---

### Task 3: Public-API regression and full verification

**Files:**
- Modify: `tests/regression/test_imports.py`

- [ ] **Step 1: Add the config exceptions to the regression guard**

In `tests/regression/test_imports.py`, in `PUBLIC_API`, after the `("piighost.exceptions", "RemoteError"),` line add:

```python
    ("piighost.exceptions", "ConfigError"),
    ("piighost.exceptions", "ConfigFileError"),
    ("piighost.exceptions", "ConfigValidationError"),
```

Do NOT add `PipelineConfig`/`load_config`/`load_pipeline` (behind the `config` extra; the walk covers the config modules, which import cleanly in the dev venv where the extra is installed).

- [ ] **Step 2: Run the regression guard, the full suite, and the checks**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/regression/test_imports.py -q`
Expected: PASS with the three new cases.

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest -q`
Expected: PASS.

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean, pyrefly 0 errors.

- [ ] **Step 3: Commit**

```bash
git add tests/regression/test_imports.py
git commit -m "test(config): guard the config exception symbols"
```

---

## Notes for the implementer

- One-way coupling is the invariant: config models import core components in their `build()`, the core never imports `piighost.config`. `test_core_no_extras.py` guards the core side; do not add any core-to-config import to satisfy a type hint (use the config-side import).
- The per-call TOML path uses a `ContextVar` set by `load_config` and read in `settings_customise_sources`, because pydantic-settings resolves sources at instantiation and the path must not be frozen at class definition. Reset the ContextVar in a `finally`.
- `LinkerConfig` is a plain alias of `ExactLinkerConfig` for now (one linker); the coverage brick turns it into a discriminated union when a second linker exists. Keep the `type: Literal["exact"]` field so the TOML declares it uniformly.
- `build()` return types are the base-tag-parameterized ports; the config path deliberately erases the precise phantom tag to the base, which is correct for a runtime-built pipeline.
- If pydantic-settings' `TomlConfigSettingsSource` signature differs in the installed version, adapt the path injection to its documented form but keep the precedence (init > env > file) and the per-call path; report the adaptation.
