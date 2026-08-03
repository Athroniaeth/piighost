# LLM Detector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `LLMDetector`, a detector that asks a LangChain chat model to extract PII as structured `(text, label)` pairs and locates each value in the source text, reusing `BaseNERDetector`'s label mapping.

**Architecture:** `LLMDetector(BaseNERDetector)` at `components/detector/llm.py`, behind the `llm` extra (`langchain-core`, which pulls in `pydantic`). It implements only the async `_raw_detect`, which formats a `ChatPromptTemplate`, awaits the structured model, and turns each extracted value into detections via `find_all_word_boundary`; the base relabels. It is exposed lazily from `components/detector/__init__.py`.

**Tech Stack:** Python 3.11+, LangChain (`langchain-core`), pydantic, pytest (`asyncio_mode = "auto"`). The `llm` extra is NOT installed in the dev venv.

---

## Conventions for every task

- Run tests with `uv run --no-sync`. Before each pytest run clear bytecode: `find src tests -name __pycache__ -type d -exec rm -rf {} +`.
- `asyncio_mode = "auto"`: `async def test_...` needs NO decorator.
- Python 3.11+ native typing, NO `from __future__ import annotations`. Docstrings plain prose plus bullet lists only, no markdown/RST. English only. Conventional Commits. flake8-annotations (ANN) is enforced on tests too, so annotate every test helper.
- `langchain-core`/`pydantic` are absent in the dev venv, so:
  - The tests use `pytest.importorskip("langchain_core")` and SKIP locally. Do not try to make them run; verify they collect and skip cleanly.
  - The `# pyrefly: ignore[invalid-argument]` on the runtime `Enum(...)` line is required (verified). The `langchain_core`/`pydantic` imports resolve for pyrefly via stubs and need only `# noqa: E402` (they follow the `find_spec` guard). `pyrefly check src/piighost` must report 0 errors.
  - `tests/regression/test_imports.py::test_every_module_imports_cleanly` walks the new module; it raises `ImportError` mentioning `piighost[llm]`, which the walk tolerates.

## File structure

- Create `src/piighost/components/detector/llm.py` — `LLMDetector` + `_make_schema`.
- Modify `src/piighost/components/detector/__init__.py` — add a lazy `__getattr__` exposing `LLMDetector`.
- Create `tests/components/detector/test_llm.py`.

---

### Task 1: LLMDetector

**Files:**
- Create: `src/piighost/components/detector/llm.py`
- Modify: `src/piighost/components/detector/__init__.py`
- Test: `tests/components/detector/test_llm.py`

- [ ] **Step 1: Write the tests**

Create `tests/components/detector/test_llm.py`:

```python
"""Tests for the LLMDetector.

The langchain-core extra is absent in the dev venv, so these tests skip via
importorskip. A fake chat model returns canned structured output, so no real LLM
or network is needed when the extra is present.
"""

import pytest

from piighost.components.detector import AnyDetector
from piighost.models import Span


class _FakeLabel:
    """A stand-in for a schema label enum member."""

    def __init__(self, value: str) -> None:
        self.value = value


class _FakeEntity:
    """A stand-in for one extracted entity."""

    def __init__(self, text: str, label: str) -> None:
        self.text = text
        self.label = _FakeLabel(label)


class _FakeExtraction:
    """A stand-in for the structured extraction result."""

    def __init__(self, entities: list[_FakeEntity]) -> None:
        self.entities = entities


class _FakeStructured:
    """A stand-in for model.with_structured_output(schema)."""

    def __init__(self, result: object) -> None:
        self._result = result

    async def ainvoke(self, messages: object, **kwargs: object) -> object:
        return self._result


class _FakeChatModel:
    """A stand-in chat model whose structured output is canned."""

    def __init__(self, result: object) -> None:
        self._result = result

    def with_structured_output(
        self, schema: object, **kwargs: object
    ) -> _FakeStructured:
        return _FakeStructured(self._result)


class TestConformance:
    def test_satisfies_the_detector_port(self) -> None:
        """LLMDetector built on an injected model is an AnyDetector."""
        pytest.importorskip("langchain_core")
        from piighost.components.detector import LLMDetector

        model = _FakeChatModel(_FakeExtraction([]))
        detector = LLMDetector(model=model, labels=["PERSON"])
        assert isinstance(detector, AnyDetector)


class TestDetect:
    async def test_locates_a_single_occurrence_and_relabels(self) -> None:
        """An extracted value is located and relabeled through the base map."""
        pytest.importorskip("langchain_core")
        from piighost.components.detector import LLMDetector

        result = _FakeExtraction([_FakeEntity("Emma", "person")])
        detector = LLMDetector(
            model=_FakeChatModel(result), labels={"PERSON": "person"}
        )
        detections = await detector.detect("Hi Emma!")
        assert len(detections) == 1
        assert detections[0].label == "PERSON"
        assert detections[0].span == Span(3, 7)
        assert detections[0].text == "Emma"
        assert detections[0].confidence == 1.0

    async def test_locates_every_occurrence(self) -> None:
        """A value present several times yields one detection each."""
        pytest.importorskip("langchain_core")
        from piighost.components.detector import LLMDetector

        result = _FakeExtraction([_FakeEntity("Emma", "PERSON")])
        detector = LLMDetector(model=_FakeChatModel(result), labels=["PERSON"])
        detections = await detector.detect("Emma and Emma")
        spans = [d.span for d in detections]
        assert spans == [Span(0, 4), Span(9, 13)]

    async def test_hallucinated_value_absent_from_text_is_ignored(self) -> None:
        """A value the model returned but that is not in the text yields none."""
        pytest.importorskip("langchain_core")
        from piighost.components.detector import LLMDetector

        result = _FakeExtraction([_FakeEntity("Bob", "PERSON")])
        detector = LLMDetector(model=_FakeChatModel(result), labels=["PERSON"])
        assert await detector.detect("Emma only") == []

    async def test_malformed_output_fails_open(self) -> None:
        """A result without an entities attribute yields no detection."""
        pytest.importorskip("langchain_core")
        from piighost.components.detector import LLMDetector

        detector = LLMDetector(model=_FakeChatModel(object()), labels=["PERSON"])
        assert await detector.detect("Emma only") == []

    async def test_empty_text_returns_empty(self) -> None:
        """Empty input yields no detection."""
        pytest.importorskip("langchain_core")
        from piighost.components.detector import LLMDetector

        result = _FakeExtraction([_FakeEntity("Emma", "PERSON")])
        detector = LLMDetector(model=_FakeChatModel(result), labels=["PERSON"])
        assert await detector.detect("") == []
```

- [ ] **Step 2: Run it to verify current state**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/components/detector/test_llm.py -q`
Expected: all tests SKIP (langchain_core absent) via `importorskip`. This confirms the file collects cleanly.

- [ ] **Step 3: Write the adapter**

Create `src/piighost/components/detector/llm.py`:

```python
"""LLM detector (optional: llm).

Wraps a LangChain chat model that extracts PII as structured (text, label)
pairs, then locates each value in the source text. This module needs the
langchain-core package (and pydantic, pulled in with it); it is guarded so
importing it without the dependency raises an ImportError pointing at the extra.
"""

import importlib.util
import logging
from enum import Enum

from piighost.components.detector.ner.base import BaseNERDetector
from piighost.models import Detection
from piighost.text import find_all_word_boundary

if importlib.util.find_spec("langchain_core") is None:
    raise ImportError(
        "LLMDetector requires the langchain-core package. "
        "Install it with: pip install piighost[llm]"
    )

from langchain_core.language_models import (  # noqa: E402
    BaseChatModel,
    init_chat_model,
)
from langchain_core.prompts import ChatPromptTemplate  # noqa: E402
from pydantic import BaseModel  # noqa: E402

logger = logging.getLogger(__name__)

_DEFAULT_PROMPT = (
    "You are a Named Entity Recognition (NER) system specialized in "
    "extracting Personally Identifiable Information (PII).\n\n"
    "Extract all entities from the user's text that match these labels:\n"
    "{labels}\n\n"
    "Return each entity exactly as it appears in the text. Only extract "
    "entities that are actually present in the text."
)


def _make_schema(labels: list[str]) -> type[BaseModel]:
    """Build a pydantic extraction model whose label field is a labels enum.

    The runtime Enum of the labels becomes an enum constraint in the JSON Schema
    that with_structured_output sends to the provider, so the model can only
    return a configured label.
    """
    label_enum = Enum("Label", [(label, label) for label in labels])  # pyrefly: ignore[invalid-argument]

    class _Entity(BaseModel):
        text: str
        label: label_enum

    class _Extraction(BaseModel):
        entities: list[_Entity]

    return _Extraction


class LLMDetector(BaseNERDetector):
    """Detect PII with a LangChain chat model via structured output.

    The model is asked to extract (text, label) pairs against a schema whose
    label field is constrained to the configured labels. Each extracted value is
    then located in the source text by word-boundary search, so a value the
    model invented but absent from the text yields nothing. labels is required,
    since the schema is built from it. A str model is loaded with init_chat_model;
    a loaded instance is used as-is.

    A custom prompt must contain a {labels} placeholder and, per LangChain's
    f-string format, double any other literal curly brace as {{ or }}. The source
    text is passed as a template value, so curly braces in it are safe.
    """

    def __init__(
        self,
        model: BaseChatModel | str,
        labels: list[str] | dict[str, str],
        prompt: str | None = None,
        provider: str | None = None,
    ) -> None:
        """Store or load the model, then build the schema, prompt, and chain."""
        super().__init__(labels)
        if isinstance(model, str):
            model = init_chat_model(model, model_provider=provider)
        self._schema = _make_schema(self.internal_labels)
        self._structured = model.with_structured_output(self._schema)
        self._prompt_template = ChatPromptTemplate.from_messages(
            [("system", prompt or _DEFAULT_PROMPT), ("human", "{text}")]
        )

    async def _raw_detect(self, text: str) -> list[Detection]:
        """Extract via the model, then locate each value in the source text."""
        if not text:
            return []

        messages = self._prompt_template.format_messages(
            labels=", ".join(self.internal_labels), text=text
        )
        result = await self._structured.ainvoke(messages)

        entities = getattr(result, "entities", None)
        if entities is None:
            logger.warning(
                "LLMDetector structured output returned no usable result "
                "(got %s); treating as no detections.",
                type(result).__name__,
            )
            return []

        detections: list[Detection] = []
        for entity in entities:
            for span in find_all_word_boundary(text, entity.text):
                detections.append(
                    Detection(
                        span=span,
                        text=text[span.start : span.end],
                        label=entity.label.value,
                        confidence=1.0,
                    )
                )
        return detections
```

Then modify `src/piighost/components/detector/__init__.py` to expose `LLMDetector` lazily. The full file becomes:

```python
"""Detectors: components that find PII in text.

AnyDetector defines the port; each module provides an adapter. The pure
detectors import eagerly; LLMDetector needs the llm extra, so it is exposed
lazily and never pulled in by importing this package.
"""

from typing import Any

from piighost.components.detector.base import AnyDetector
from piighost.components.detector.chunked import ChunkedDetector
from piighost.components.detector.composite import CompositeDetector
from piighost.components.detector.exact import ExactMatchDetector
from piighost.components.detector.regex import RegexDetector

__all__ = [
    "AnyDetector",
    "ChunkedDetector",
    "CompositeDetector",
    "ExactMatchDetector",
    "LLMDetector",
    "RegexDetector",
]


def __getattr__(name: str) -> Any:
    """Import LLMDetector on demand so its optional extra stays optional."""
    if name == "LLMDetector":
        from piighost.components.detector.llm import LLMDetector

        return LLMDetector

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

- [ ] **Step 4: Run the LLM tests and the import walk**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/components/detector/test_llm.py tests/regression/test_imports.py -q`
Expected: the LLM tests SKIP (langchain_core absent); `test_imports.py` passes, its walk importing `piighost.components.detector.llm` raises ImportError mentioning `piighost[llm]`, tolerated.

- [ ] **Step 5: Run the full suite and checks**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest -q`
Expected: PASS. The LLM tests skip; everything else green.

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean over the whole repo; pyrefly 0 errors under `src/piighost` (the `Enum` line is the one suppression).

- [ ] **Step 6: Commit**

```bash
git add src/piighost/components/detector/llm.py src/piighost/components/detector/__init__.py tests/components/detector/test_llm.py
git commit -m "feat(detector): add the LLM detector"
```

---

## Notes for the implementer

- `langchain-core` / `pydantic` are deliberately absent from the dev venv. Do not install them. The tests skip via `importorskip`; that is the correct outcome. The real logic that runs locally is the base label mapping (already tested) plus the import-guard walk; the fake-model tests exercise occurrence-location and fail-open when the extra is present.
- Only ONE pyrefly suppression is expected, `# pyrefly: ignore[invalid-argument]` on the `Enum("Label", ...)` line. The `langchain_core`/`pydantic` imports resolve for pyrefly (stubs) and need only `# noqa: E402`. If pyrefly reports anything else, report it rather than scattering suppressions; do not add a suppression that pyrefly says is unused.
- `LLMDetector` is NOT added to `tests/regression/test_imports.py` PUBLIC_API: a `hasattr` probe would trigger its lazy import and fail with the extra absent. The `test_every_module_imports_cleanly` walk already covers it.
- Do not add `from_config` or config models; the `model | str` + `provider` constructor absorbs model loading, and the config block is later.
- `find_all_word_boundary(text, fragment)` returns `list[Span]` and is case-insensitive by default, so `text[span.start:span.end]` recovers the source casing.
