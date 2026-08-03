# HITL Corrected Detections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `anonymize_corrected` on `ThreadAnonymizationPipeline`: persist a human-corrected detection set for a user message and re-anonymize it with thread-consistent tokens.

**Architecture:** A thin method that calls `memory.remember` to replace the message's cached detections with the corrected set (as a `USER` message), then delegates to `anonymize`, whose `_detect` reads the just-written cache so no detector runs and thread token assignment honors the correction.

**Tech Stack:** Python 3.11+, pytest (`asyncio_mode = "auto"`). Deterministic tests with `ExactMatchDetector`, no model.

---

## Conventions for every task

- Run tests with `uv run --no-sync`. Before each pytest run clear bytecode: `find src tests -name __pycache__ -type d -exec rm -rf {} +`.
- `asyncio_mode = "auto"`: `async def test_...` needs NO decorator.
- Python 3.11+ native typing, NO `from __future__ import annotations`. Docstrings plain prose plus bullet lists only, no markdown/RST. English only. Conventional Commits. flake8-annotations (ANN) is enforced on tests too, so annotate every test helper.

## File structure

- Modify `src/piighost/pipeline/thread.py` — add the `anonymize_corrected` method.
- Create `tests/pipeline/test_thread_hitl.py` — the correction tests.

No regression-guard change: `anonymize_corrected` is a method on the already-exported `ThreadAnonymizationPipeline`, not a new module symbol.

---

### Task 1: anonymize_corrected

**Files:**
- Modify: `src/piighost/pipeline/thread.py`
- Test: `tests/pipeline/test_thread_hitl.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/pipeline/test_thread_hitl.py`:

```python
"""Tests for the ThreadAnonymizationPipeline HITL correction method."""

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import AnyDetector, ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.models import Detection, Span
from piighost.pipeline import ThreadAnonymizationPipeline


def _pipeline(detector: AnyDetector | None = None) -> ThreadAnonymizationPipeline:
    """Build a thread pipeline over a counter factory and in-memory backend."""
    return ThreadAnonymizationPipeline(
        detector or ExactMatchDetector({"Paris": "LOCATION"}),
        ExactEntityLinker(),
        Anonymizer(LabelCounterPlaceholderFactory()),
        InMemoryConversationMemory(),
    )


def _acme() -> list[Detection]:
    """A one-detection corrected set naming Acme at the start of the text."""
    return [Detection(span=Span(0, 4), text="Acme", label="ORG", confidence=1.0)]


class TestAnonymizeCorrected:
    async def test_adds_a_missed_value(self) -> None:
        """A corrected set adds a value the detector never found."""
        pipeline = _pipeline(ExactMatchDetector({}))
        result = await pipeline.anonymize_corrected("Acme rocks", "t1", _acme())
        assert result.text == "<<ORG:1>> rocks"

    async def test_drops_a_false_positive(self) -> None:
        """An empty corrected set leaves a mis-detected value in clear."""
        pipeline = _pipeline()
        first = await pipeline.anonymize("Visit Paris", "t1")
        assert first.text == "Visit <<LOCATION:1>>"
        corrected = await pipeline.anonymize_corrected("Visit Paris", "t1", [])
        assert corrected.text == "Visit Paris"

    async def test_added_value_is_deanonymizable_thread_wide(self) -> None:
        """A corrected addition enters the thread token map and is reversible."""
        pipeline = _pipeline(ExactMatchDetector({}))
        await pipeline.anonymize_corrected("Acme rocks", "t1", _acme())
        restored = await pipeline.deanonymize("<<ORG:1>>", "t1")
        assert restored == "Acme"

    async def test_correction_is_local_to_the_message(self) -> None:
        """Dropping a value from one message does not clear it in another."""
        pipeline = _pipeline()
        await pipeline.anonymize("Visit Paris", "t1")
        await pipeline.anonymize_corrected("Visit Paris", "t1", [])
        later = await pipeline.anonymize("Go to Paris", "t1")
        assert later.text == "Go to <<LOCATION:1>>"

    async def test_re_correcting_replaces_cleanly(self) -> None:
        """A second corrected set replaces the first rather than merging."""
        pipeline = _pipeline(ExactMatchDetector({}))
        await pipeline.anonymize_corrected("Acme rocks", "t1", _acme())
        replaced = await pipeline.anonymize_corrected("Acme rocks", "t1", [])
        assert replaced.text == "Acme rocks"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/pipeline/test_thread_hitl.py -q`
Expected: FAIL with `AttributeError: 'ThreadAnonymizationPipeline' object has no attribute 'anonymize_corrected'`.

- [ ] **Step 3: Add the method**

In `src/piighost/pipeline/thread.py`, add the `anonymize_corrected` method to `ThreadAnonymizationPipeline`, directly after the `anonymize` method (before `deanonymize`). No new imports are needed: `Anonymization`, `Detection`, and `MessageRole` are already imported at the top of the file.

```python
    async def anonymize_corrected(
        self,
        text: str,
        thread_id: str,
        detections: list[Detection],
    ) -> Anonymization[PreservationT]:
        """Re-anonymize a user message with a human-corrected detection set.

        The corrected set replaces this message's detections in memory, then the
        message is re-anonymized with tokens consistent across the thread.
        Detection does not run again, since the correction is read from the
        cache. Only a user's own messages are corrected this way, so the
        correction is recorded as a user message. The corrected set is stored as
        given, without overlap resolution or occurrence expansion, since the
        human is authoritative over it.
        """
        await self.memory.remember(
            thread_id=thread_id,
            message=text,
            detections=detections,
            role=MessageRole.USER,
        )
        return await self.anonymize(text, thread_id, MessageRole.USER)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/pipeline/test_thread_hitl.py -q`
Expected: PASS, 5 passed.

- [ ] **Step 5: Run the full suite and checks**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest -q`
Expected: PASS, no regressions.

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean over the whole repo; pyrefly 0 errors under `src/piighost`.

- [ ] **Step 6: Commit**

```bash
git add src/piighost/pipeline/thread.py tests/pipeline/test_thread_hitl.py
git commit -m "feat(pipeline): add a HITL corrected-detections method to the thread pipeline"
```

---

## Notes for the implementer

- The method is deliberately thin: `remember` then `anonymize`. Do not re-implement detection, linking, or rendering; `anonymize` already does all of it, and its `_detect` reads the cache the `remember` call just wrote, so the detector does not run.
- There is NO `role` parameter: a human corrects only their own messages, so the correction is always recorded as `MessageRole.USER`.
- The corrected set replaces the message's memory entry wholesale (delta semantics are out of scope). An empty list is valid and means the message holds no PII.
- The correction is local to the corrected message. It changes the thread's detection union (so an added value becomes deanonymizable thread-wide, and token numbering accounts for it), but it does not retroactively tokenize the value in other already-cached messages, nor un-tokenize it in a message that detects it on its own. The tests lock exactly this behavior.
- `deanonymize` on the thread pipeline is async (`await pipeline.deanonymize(...)`).
