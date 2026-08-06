# Config Coverage D: Remote Client and JSON Format Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the config loaders accept a JSON file as well as TOML, and add a `load_client` entry that builds a remote PIIGhostClient from a ClientConfig.

**Architecture:** `settings.py` keeps one path ContextVar (renamed `_config_path`) and a `_file_source` helper that picks a JSON or TOML settings source by file suffix; a `_read` helper factors the parse-and-map-errors logic shared by `load_config` and the new `load_client`. `ClientConfig` is a top-level settings model peer to `PipelineConfig`, living in `settings.py`.

**Tech Stack:** Python 3.11+, pydantic-settings (TomlConfigSettingsSource + JsonConfigSettingsSource). Dev has httpx, and building a PIIGhostClient does not connect, so build() is tested offline.

---

## Conventions

- Run with `uv run --no-sync`. Before each pytest run: `find src tests -name __pycache__ -type d -exec rm -rf {} +`.
- English only. Docstrings plain prose + bullet lists (no markdown/RST). No em dash. No `from __future__`. Native 3.11+ typing. Conventional Commits. Do NOT push. Do NOT create `__init__.py` under `tests/`.
- ANN enforced on src and tests.
- `PIIGhostClient` is behind the client extra (httpx); import it lazily inside build() and annotate it as a string with a TYPE_CHECKING import, so settings.py does not require httpx.

## Verified facts (rely on these)

- `pydantic_settings.JsonConfigSettingsSource(settings_cls, json_file=path)` exists, same shape as `TomlConfigSettingsSource(settings_cls, toml_file=path)`.
- Current `settings.py` has `_toml_path: ContextVar[Path | None]`, `PipelineConfig.settings_customise_sources` building `TomlConfigSettingsSource` from it, and `load_config` with the inline try/except mapping `tomllib.TOMLDecodeError`/`OSError` -> `ConfigFileError` and `ValidationError` -> `ConfigValidationError`. `load_pipeline`/`load_thread_pipeline` call `load_config(path).build()`.
- `json.JSONDecodeError` (a ValueError subclass, distinct from pydantic's ValidationError) is raised on malformed JSON at `PipelineConfig()` construction time.
- `PIIGhostClient(client: httpx.AsyncClient | str, recognizer=None)` in `piighost.integrations.client` (lazy export, extra client). A `str` base URL builds an `httpx.AsyncClient(base_url=...)` offline; `recognizer` defaults to `LabelCounterPlaceholderFactory()`. `client.recognizer` returns it.
- `PIIGhostClient` satisfies the `AnyThreadPipeline` port (`piighost.pipeline`). httpx is in the dev env.
- `RegexDetectorConfig` has `type: Literal["regex"]`, so a parsed `config.detector.type == "regex"`.

---

### Task 1: JSON file format

**Files:**
- Modify: `src/piighost/config/settings.py`
- Test: `tests/config/test_json.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/config/test_json.py`:

```python
"""Tests for loading a config from a JSON file."""

import json
from pathlib import Path

import pytest

from piighost.config import load_config, load_pipeline
from piighost.exceptions import ConfigFileError

_CONFIG = {
    "detector": {"type": "regex", "patterns": {"EMAIL": "[a-z]+@[a-z.]+"}},
    "linker": {"type": "exact"},
    "anonymizer": {"placeholder": {"type": "redact"}},
}


def _write_json(tmp_path: Path, data: dict[str, object]) -> Path:
    """Write data as JSON to a config.json under tmp_path and return the path."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data))
    return path


class TestLoadJson:
    def test_valid_json_parses(self, tmp_path: Path) -> None:
        """A valid JSON file parses into a PipelineConfig."""
        config = load_config(_write_json(tmp_path, _CONFIG))
        assert config.detector.type == "regex"

    async def test_json_builds_a_working_pipeline(self, tmp_path: Path) -> None:
        """load_pipeline on a JSON file anonymizes end to end."""
        pipeline = load_pipeline(_write_json(tmp_path, _CONFIG))
        result = await pipeline.anonymize("reach a@b.co now")
        assert result.text == "reach <<REDACT>> now"

    def test_invalid_json_raises_config_file_error(self, tmp_path: Path) -> None:
        """A syntactically invalid JSON file raises ConfigFileError."""
        path = tmp_path / "config.json"
        path.write_text("{ not valid json")
        with pytest.raises(ConfigFileError):
            load_config(path)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/config/test_json.py -q`
Expected: FAIL (the `.json` file is loaded through the TOML source and raises a TOML decode error mapped oddly, or the invalid-json test does not raise ConfigFileError, because JSON is not yet wired). Note the exact failure.

- [ ] **Step 3: Wire the JSON source and factor the loader**

In `src/piighost/config/settings.py`, READ the file first, then make these edits.

(a) Add `import json` above `import tomllib`:

```python
import json
import tomllib
```

(b) Add `TypeVar` to the typing import (keep `ClassVar`, `cast`):

```python
from typing import ClassVar, TypeVar, cast
```

(c) Add `JsonConfigSettingsSource` to the pydantic_settings import (alphabetical):

```python
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)
```

(d) Rename the module ContextVar from `_toml_path` to `_config_path` (declaration and its docstring), and add the `_file_source` helper and a `_ConfigT` TypeVar right after it:

```python
_config_path: ContextVar[Path | None] = ContextVar("_config_path", default=None)
"""The config file the current load reads, set by a loader, read by the source."""

_ConfigT = TypeVar("_ConfigT", bound=BaseSettings)


def _file_source(settings_cls: type[BaseSettings]) -> PydanticBaseSettingsSource | None:
    """The file settings source for the current load, JSON or TOML by suffix.

    Returns None when no path is set, so init and env still apply on their own.
    """
    path = _config_path.get()
    if path is None:
        return None
    if path.suffix == ".json":
        return JsonConfigSettingsSource(settings_cls, json_file=path)
    return TomlConfigSettingsSource(settings_cls, toml_file=path)
```

(e) Replace the body of `PipelineConfig.settings_customise_sources` (the docstring line and the source-building lines) with:

```python
        """Layer init, then env, then the config file the current load points at."""
        sources: list[PydanticBaseSettingsSource] = [init_settings, env_settings]
        file_source = _file_source(settings_cls)
        if file_source is not None:
            sources.append(file_source)
        return tuple(sources)
```

(f) Replace the entire `load_config` function with a `_read` helper plus a thin `load_config`:

```python
def _read(config_cls: type[_ConfigT], path: str | Path) -> _ConfigT:
    """Parse a TOML or JSON file into the given settings model.

    Raises:
        ConfigFileError: If the file is missing, unreadable, or invalid TOML/JSON.
        ConfigValidationError: If the parsed data fails schema validation.
    """
    resolved = Path(path)
    if not resolved.is_file():
        raise ConfigFileError(f"configuration file not found: {resolved}")

    token = _config_path.set(resolved)
    try:
        return config_cls()
    except (tomllib.TOMLDecodeError, json.JSONDecodeError) as exc:
        raise ConfigFileError(f"invalid config file {resolved}: {exc}") from exc
    except OSError as exc:
        raise ConfigFileError(f"cannot read {resolved}: {exc}") from exc
    except ValidationError as exc:
        raise ConfigValidationError(
            f"invalid configuration in {resolved}: {exc}"
        ) from exc
    finally:
        _config_path.reset(token)


def load_config(path: str | Path) -> PipelineConfig:
    """Parse and validate a config file into a PipelineConfig, building nothing.

    The file may be TOML or JSON, chosen by its suffix.

    Raises:
        ConfigFileError: If the file is missing, unreadable, or invalid TOML/JSON.
        ConfigValidationError: If the parsed data fails schema validation.
    """
    return _read(PipelineConfig, path)
```

Leave `load_pipeline` and `load_thread_pipeline` unchanged (they call `load_config`).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/config/ -q`
Expected: PASS (the JSON tests plus every pre-existing config test; the ContextVar rename and `_read` extraction preserve TOML behavior).

- [ ] **Step 5: Lint, types, commit**

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: clean, 0 errors.

```bash
git add src/piighost/config/settings.py tests/config/test_json.py
git commit -m "feat(config): accept a JSON config file alongside TOML"
```

---

### Task 2: Remote client config

**Files:**
- Modify: `src/piighost/config/settings.py`
- Modify: `src/piighost/config/__init__.py`
- Test: `tests/config/test_client_config.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/config/test_client_config.py`:

```python
"""Tests for the remote client config."""

from pathlib import Path

from piighost.components.placeholder.label_counter import (
    LabelCounterPlaceholderFactory,
)
from piighost.config import load_client
from piighost.config.settings import ClientConfig
from piighost.integrations.client import PIIGhostClient
from piighost.pipeline import AnyThreadPipeline

_BASE_URL = "http://localhost:8000"


class TestClientConfig:
    def test_builds_a_client(self) -> None:
        """The client config builds a PIIGhostClient over its base URL."""
        client = ClientConfig(base_url=_BASE_URL).build()
        assert isinstance(client, PIIGhostClient)

    def test_recognizer_defaults_to_label_counter(self) -> None:
        """The built client's recognizer is the standard label-counter grammar."""
        client = ClientConfig(base_url=_BASE_URL).build()
        assert isinstance(client.recognizer, LabelCounterPlaceholderFactory)

    def test_conforms_to_the_thread_pipeline_port(self) -> None:
        """A built client satisfies the AnyThreadPipeline port."""
        client = ClientConfig(base_url=_BASE_URL).build()
        assert isinstance(client, AnyThreadPipeline)


class TestLoadClient:
    def test_loads_from_toml(self, tmp_path: Path) -> None:
        """load_client builds a PIIGhostClient from a TOML file."""
        path = tmp_path / "client.toml"
        path.write_text('base_url = "http://localhost:8000"\n')
        assert isinstance(load_client(path), PIIGhostClient)

    def test_loads_from_json(self, tmp_path: Path) -> None:
        """load_client builds a PIIGhostClient from a JSON file."""
        path = tmp_path / "client.json"
        path.write_text('{"base_url": "http://localhost:8000"}')
        assert isinstance(load_client(path), PIIGhostClient)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/config/test_client_config.py -q`
Expected: FAIL with `ImportError: cannot import name 'ClientConfig'` (or `load_client`).

- [ ] **Step 3: Add ClientConfig and load_client to settings.py**

In `src/piighost/config/settings.py`:

(a) Add a TYPE_CHECKING import for the client type (after the `TypeVar` import edit from Task 1, add `TYPE_CHECKING` to the typing import and a guarded import block near the other imports):

```python
from typing import TYPE_CHECKING, ClassVar, TypeVar, cast
```

And, after the existing imports (below `from piighost.pipeline import (...)`), add:

```python
if TYPE_CHECKING:
    from piighost.integrations.client import PIIGhostClient
```

(b) Append `ClientConfig` and `load_client` at the END of the file:

```python
class ClientConfig(BaseSettings):
    """Configuration for a remote PIIGhostClient.

    Attributes:
        base_url: The base URL of the piighost-api server the client calls.
    """

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="PIIGHOST_", extra="forbid"
    )

    base_url: str

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Layer init, then env, then the config file the current load points at."""
        sources: list[PydanticBaseSettingsSource] = [init_settings, env_settings]
        file_source = _file_source(settings_cls)
        if file_source is not None:
            sources.append(file_source)
        return tuple(sources)

    def build(self) -> "PIIGhostClient":
        """Build a PIIGhostClient over the configured base URL."""
        from piighost.integrations.client import PIIGhostClient

        return PIIGhostClient(self.base_url)


def load_client(path: str | Path) -> "PIIGhostClient":
    """Load a configuration and build its remote PIIGhostClient.

    The file may be TOML or JSON, chosen by its suffix.

    Raises:
        ConfigFileError: If the file is missing, unreadable, or invalid TOML/JSON.
        ConfigValidationError: If the parsed data fails schema validation.
    """
    return _read(ClientConfig, path).build()
```

- [ ] **Step 4: Export from the config package**

In `src/piighost/config/__init__.py`, extend the settings import and `__all__`:

```python
from piighost.config.settings import (  # noqa: E402
    ClientConfig,
    PipelineConfig,
    load_client,
    load_config,
    load_pipeline,
    load_thread_pipeline,
)

__all__ = [
    "ClientConfig",
    "PipelineConfig",
    "load_client",
    "load_config",
    "load_pipeline",
    "load_thread_pipeline",
]
```

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
git add src/piighost/config/settings.py src/piighost/config/__init__.py tests/config/test_client_config.py
git commit -m "feat(config): add the remote client config and load_client"
```

---

## Notes for the implementer

- The format is chosen by the file suffix in `_file_source`: `.json` uses `JsonConfigSettingsSource`, anything else uses `TomlConfigSettingsSource`. This gives JSON to `load_config`, `load_pipeline`, and `load_thread_pipeline` for free, since they all route through `_read`.
- `ClientConfig` lives in `settings.py`, a peer of `PipelineConfig`, NOT in `config/models/`. A client model in `config/models/` would import `_file_source` from `settings.py` and create an import cycle.
- `PIIGhostClient` is imported lazily inside `build()` and annotated as a string with a TYPE_CHECKING import, so importing `settings.py` never requires httpx. `load_client` needs `piighost[config,client]`; a missing httpx surfaces as the client module's ImportError at build().
- The client `base_url` is a top-level key in the config file (like `detector`/`linker` for a pipeline config), not nested under a `[client]` table. The recognizer stays at its default (YAGNI).
- Keep the one-way coupling: config imports core, never the reverse. No new exception, nothing added to `PUBLIC_API`.
