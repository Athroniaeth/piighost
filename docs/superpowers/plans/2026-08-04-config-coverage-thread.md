# Config Coverage C1: Thread Pipeline and In-Memory Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a TOML config describe a stateful thread pipeline by adding an optional `memory` field to PipelineConfig, an InMemoryConfig model, a polymorphic build(), and a typed `load_thread_pipeline` entry point.

**Architecture:** `PipelineConfig.build()` assembles the stages once, then returns a ThreadAnonymizationPipeline when a memory is configured or an AnonymizationPipeline otherwise, typed as the shared base. Two entry points narrow the result: `load_pipeline` (rejects a memory config) and `load_thread_pipeline` (requires one).

**Tech Stack:** Python 3.11+, pydantic-settings, the existing ThreadAnonymizationPipeline and InMemoryConversationMemory (no extra).

---

## Conventions

- Run with `uv run --no-sync`. Before each pytest run: `find src tests -name __pycache__ -type d -exec rm -rf {} +`.
- English only. Docstrings plain prose + bullet lists (no markdown/RST). No em dash. No `from __future__`. Native 3.11+ typing. Conventional Commits. Do NOT push. Do NOT create `__init__.py` under `tests/`.
- ANN enforced on src and tests.
- If pyrefly flags the isinstance-narrowed generic return, use `cast` as shown below (do not weaken the annotation).

## Verified facts (rely on these)

- `piighost.pipeline` exports `AnonymizationPipeline`, `BaseAnonymizationPipeline`, `ThreadAnonymizationPipeline` (all eager, no extra). `AnonymizationPipeline` and `ThreadAnonymizationPipeline` are siblings, both extend `BaseAnonymizationPipeline`; neither subclasses the other, so an isinstance check on one excludes the other.
- `ThreadAnonymizationPipeline.__init__(detector, linker, anonymizer, memory, overlap_resolver=None, expander=None, entity_resolver=None, guard=None, observation_redactor=None, override=None)`. `anonymize(text, thread_id, role=MessageRole.USER)` with thread_id REQUIRED (no default).
- `piighost.conversation_memory` eagerly exports `InMemoryConversationMemory` (no extra); its `AnyConversationMemory` port is in `piighost.conversation_memory.base`. `InMemoryConversationMemory()` takes no arguments.
- `ExactMatchDetectorConfig` (type "exact", `values: dict[str,str]`) and the `label_counter` placeholder exist and are in the config unions (from earlier sub-lots). `ExactMatchDetector` is case-sensitive, so it matches "Patrick" literally.
- Current `settings.py` imports `from piighost.pipeline import AnonymizationPipeline` and `from piighost.exceptions import ConfigFileError, ConfigValidationError`; `PipelineConfig.build()` returns `AnonymizationPipeline[PlaceholderPreservation]`; `load_pipeline` is `return load_config(path).build()`. The config model imports are alphabetical.

---

### Task 1: Thread pipeline config and in-memory backend

**Files:**
- Create: `src/piighost/config/models/memory.py`
- Modify: `src/piighost/config/settings.py`
- Modify: `src/piighost/config/__init__.py`
- Test: `tests/config/test_thread.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/config/test_thread.py`:

```python
"""Tests for building a thread pipeline from config."""

from pathlib import Path

import pytest

from piighost.config import load_pipeline, load_thread_pipeline
from piighost.config.models.memory import InMemoryConfig
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.exceptions import ConfigError
from piighost.pipeline import AnonymizationPipeline, ThreadAnonymizationPipeline

_THREAD_TOML = """
[detector]
type = "exact"
values = { Patrick = "PERSON" }

[linker]
type = "exact"

[anonymizer.placeholder]
type = "label_counter"

[memory]
type = "in_memory"
"""

_SIMPLE_TOML = """
[detector]
type = "exact"
values = { Patrick = "PERSON" }

[linker]
type = "exact"

[anonymizer.placeholder]
type = "label_counter"
"""


def _write(tmp_path: Path, text: str) -> Path:
    """Write text to a config.toml under tmp_path and return the path."""
    path = tmp_path / "config.toml"
    path.write_text(text)
    return path


class TestInMemoryConfig:
    def test_builds_an_in_memory_backend(self) -> None:
        """The in_memory config builds an InMemoryConversationMemory."""
        memory = InMemoryConfig(type="in_memory").build()
        assert isinstance(memory, InMemoryConversationMemory)


class TestLoadThreadPipeline:
    def test_builds_a_thread_pipeline(self, tmp_path: Path) -> None:
        """load_thread_pipeline builds a ThreadAnonymizationPipeline."""
        pipeline = load_thread_pipeline(_write(tmp_path, _THREAD_TOML))
        assert isinstance(pipeline, ThreadAnonymizationPipeline)

    async def test_memory_shares_placeholder_across_messages(
        self, tmp_path: Path
    ) -> None:
        """A thread reuses an entity's token across messages via its memory."""
        pipeline = load_thread_pipeline(_write(tmp_path, _THREAD_TOML))
        first = await pipeline.anonymize("hi Patrick", "t")
        second = await pipeline.anonymize("bye Patrick", "t")
        assert "<<PERSON:1>>" in first.text
        assert "<<PERSON:1>>" in second.text

    def test_missing_memory_is_rejected(self, tmp_path: Path) -> None:
        """load_thread_pipeline on a config without memory raises ConfigError."""
        with pytest.raises(ConfigError):
            load_thread_pipeline(_write(tmp_path, _SIMPLE_TOML))


class TestLoadPipelineRejectsMemory:
    def test_memory_config_is_rejected(self, tmp_path: Path) -> None:
        """load_pipeline on a config declaring a memory raises ConfigError."""
        with pytest.raises(ConfigError):
            load_pipeline(_write(tmp_path, _THREAD_TOML))

    async def test_simple_config_still_builds(self, tmp_path: Path) -> None:
        """load_pipeline on a memory-less config still builds a simple pipeline."""
        pipeline = load_pipeline(_write(tmp_path, _SIMPLE_TOML))
        assert isinstance(pipeline, AnonymizationPipeline)
        result = await pipeline.anonymize("hi Patrick")
        assert "<<PERSON:1>>" in result.text
```

- [ ] **Step 2: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/config/test_thread.py -q`
Expected: FAIL with `ImportError: cannot import name 'load_thread_pipeline'` (or `No module named 'piighost.config.models.memory'`).

- [ ] **Step 3: Create the memory model**

Create `src/piighost/config/models/memory.py`:

```python
"""Conversation memory configuration model."""

from typing import Literal

from piighost.config.models.common import _ComponentConfig
from piighost.conversation_memory.base import AnyConversationMemory


class InMemoryConfig(_ComponentConfig):
    """Config for the in-memory conversation memory, a process-local store."""

    type: Literal["in_memory"]

    def build(self) -> AnyConversationMemory:
        """Build an InMemoryConversationMemory."""
        from piighost.conversation_memory import InMemoryConversationMemory

        return InMemoryConversationMemory()


MemoryConfig = InMemoryConfig
"""The conversation memory configuration.

A plain alias while one backend exists; it becomes a discriminated union when
the redis backend lands.
"""
```

- [ ] **Step 4: Wire memory into settings.py**

In `src/piighost/config/settings.py`, make these edits.

(a) Add `cast` to the typing import:

```python
from typing import ClassVar, cast
```

(b) Widen the pipeline import:

```python
from piighost.pipeline import (
    AnonymizationPipeline,
    BaseAnonymizationPipeline,
    ThreadAnonymizationPipeline,
)
```

(c) Add `ConfigError` to the exceptions import:

```python
from piighost.exceptions import ConfigError, ConfigFileError, ConfigValidationError
```

(d) Add the memory-model import (alphabetically, after the `linker` import line):

```python
from piighost.config.models.memory import MemoryConfig
```

(e) Add the `memory` field to `PipelineConfig`, immediately after the `observation_redactor` field, and add a matching line to the class docstring's Attributes section:

```python
    observation_redactor: PlaceholderConfig | None = None
    memory: MemoryConfig | None = None
```

Add to the Attributes section:

```
        memory: The optional conversation memory; when set, the pipeline is a
            thread pipeline keeping per-thread state.
```

(f) Replace the entire `build()` method with the polymorphic version:

```python
    def build(self) -> BaseAnonymizationPipeline[PlaceholderPreservation]:
        """Assemble the pipeline the configuration describes.

        A configured memory yields a ThreadAnonymizationPipeline keeping a
        per-thread conversation memory; without it, a stateless
        AnonymizationPipeline.
        """
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
        if self.memory is not None:
            return ThreadAnonymizationPipeline(
                detector,
                linker,
                anonymizer,
                memory=self.memory.build(),
                overlap_resolver=overlap_resolver,
                expander=expander,
                entity_resolver=entity_resolver,
                guard=guard,
                observation_redactor=observation_redactor,
                override=override,
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

(g) Replace the `load_pipeline` function and add `load_thread_pipeline` after it:

```python
def load_pipeline(path: str | Path) -> AnonymizationPipeline[PlaceholderPreservation]:
    """Load a configuration and build its stateless AnonymizationPipeline.

    Raises:
        ConfigError: If the configuration declares a memory, which describes a
            thread pipeline; use load_thread_pipeline instead.
    """
    pipeline = load_config(path).build()
    if not isinstance(pipeline, AnonymizationPipeline):
        raise ConfigError(
            "this configuration declares a memory; use load_thread_pipeline"
        )
    return cast(AnonymizationPipeline[PlaceholderPreservation], pipeline)


def load_thread_pipeline(
    path: str | Path,
) -> ThreadAnonymizationPipeline[PlaceholderPreservation]:
    """Load a configuration and build its ThreadAnonymizationPipeline.

    Raises:
        ConfigError: If the configuration declares no memory, which a thread
            pipeline needs; use load_pipeline instead.
    """
    pipeline = load_config(path).build()
    if not isinstance(pipeline, ThreadAnonymizationPipeline):
        raise ConfigError(
            "this configuration declares no memory; use load_pipeline"
        )
    return cast(ThreadAnonymizationPipeline[PlaceholderPreservation], pipeline)
```

- [ ] **Step 5: Export load_thread_pipeline**

In `src/piighost/config/__init__.py`, extend the import and `__all__`:

```python
from piighost.config.settings import (  # noqa: E402
    PipelineConfig,
    load_config,
    load_pipeline,
    load_thread_pipeline,
)

__all__ = ["PipelineConfig", "load_config", "load_pipeline", "load_thread_pipeline"]
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/config/ -q`
Expected: PASS (the new thread tests plus the pre-existing config tests, which use memory-less configs, stay green).

- [ ] **Step 7: Full suite, lint, types**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest -q`
Expected: full suite PASS.

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: clean, 0 errors.

- [ ] **Step 8: Commit**

```bash
git add src/piighost/config/models/memory.py src/piighost/config/settings.py src/piighost/config/__init__.py tests/config/test_thread.py
git commit -m "feat(config): build a thread pipeline with an in-memory backend"
```

---

## Notes for the implementer

- `build()`'s return type widens to `BaseAnonymizationPipeline[PlaceholderPreservation]`. The two entry points narrow it with isinstance and a `cast` (isinstance loses the generic parameter, so the cast restores it without weakening the public signature).
- `load_pipeline` now rejects a memory-declaring config rather than silently dropping the memory, since such a config describes a thread pipeline. This is intentional and the reason the new thread test `TestLoadPipelineRejectsMemory` exists.
- Keep the one-way coupling: settings.py and memory.py import core, never the reverse. No new exception (ConfigError already exists), nothing added to `PUBLIC_API` (load_thread_pipeline is behind the config extra, covered by the module walk).
- The memory-sharing test relies on the thread pipeline reusing an entity's counter across messages in one thread. If the second message does not reproduce `<<PERSON:1>>`, stop and report it as a concern rather than changing the assertion, since that would signal a real pipeline behavior difference.
