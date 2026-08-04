# Detection Overrides Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `DetectionOverride`, a detector-driven whitelist/blacklist stage applied right after detection and at the thread memory write points, so server decisions trump both the detector and HITL corrections.

**Architecture:** New pure package `components/override/`: two strategy enums, an `AnyDetectionOverride` port (`apply` + `cleared_values`), and `DetectionOverride(whitelist, blacklist, ...)` whose lists are `AnyDetector`s. The pipelines gain an `override` parameter; the base applies it between detect and overlap resolution, the thread applies it on the fresh detect path and on corrected sets before `remember`, and blacklist-matched values feed the guard's `expected` exemption.

**Tech Stack:** Python 3.11+, pytest (`asyncio_mode = "auto"`). No optional dependency: eager exports.

---

## Conventions for every task

- Run tests with `uv run --no-sync`. Before each pytest run clear bytecode: `find src tests -name __pycache__ -type d -exec rm -rf {} +`.
- `asyncio_mode = "auto"`: `async def test_...` needs NO decorator. flake8-annotations (ANN) is enforced on tests too.
- Python 3.11+ native typing, NO `from __future__ import annotations`. Docstrings plain prose plus bullet lists only, no markdown/RST. English only. Conventional Commits.
- `Detection(span=Span(start, end), text=..., label=..., confidence=...)` is a frozen ordered dataclass with `overlaps(other)`; `Span` is half-open with `overlaps`. `ExactMatchDetector({"value": "LABEL"})` finds literal occurrences.
- No pyrefly suppression is expected anywhere; `pyrefly check src/piighost` must stay at 0 errors.

## File structure

- Modify `src/piighost/exceptions.py` — `OverrideError`, `ConflictingOverrideError` (Task 1).
- Create `src/piighost/components/override/strategy.py` — the two enums (Task 1).
- Create `src/piighost/components/override/base.py` — the port (Task 1).
- Create `src/piighost/components/override/detector.py` — `DetectionOverride` (Task 1).
- Create `src/piighost/components/override/__init__.py` — eager exports (Task 1).
- Modify `src/piighost/pipeline/base.py` — `override` param, stage, guard exemption (Task 2).
- Modify `tests/observation/test_pipeline_spans.py` — override stage span (Task 2).
- Modify `src/piighost/pipeline/thread.py` — write-point application, guard merge (Task 3).
- Modify `tests/regression/test_imports.py` — new public symbols (Task 4).
- Tests: `tests/components/override/test_override.py`, `tests/pipeline/test_override_integration.py`.

---

### Task 1: The DetectionOverride component

**Files:**
- Modify: `src/piighost/exceptions.py`
- Create: `src/piighost/components/override/strategy.py`
- Create: `src/piighost/components/override/base.py`
- Create: `src/piighost/components/override/detector.py`
- Create: `src/piighost/components/override/__init__.py`
- Test: `tests/components/override/test_override.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/components/override/test_override.py`:

```python
"""Tests for the DetectionOverride component."""

import pytest

from piighost.components.detector import ExactMatchDetector
from piighost.components.override import (
    AnyDetectionOverride,
    BlacklistStrategy,
    DetectionOverride,
    OverrideConflictStrategy,
)
from piighost.exceptions import ConflictingOverrideError
from piighost.models import Detection, Span


def _detection(
    start: int, end: int, text: str, label: str = "PERSON", confidence: float = 0.8
) -> Detection:
    """Build a detection covering [start, end) for the given text and label."""
    span = Span(start, end)
    return Detection(
        span=span,
        text=text,
        label=label,
        confidence=confidence,
    )


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """DetectionOverride is an AnyDetectionOverride."""
        assert isinstance(DetectionOverride(), AnyDetectionOverride)


class TestEmpty:
    async def test_no_lists_leave_detections_unchanged(self) -> None:
        """A component with neither list configured passes detections through."""
        primary = [_detection(0, 4, "Emma")]
        result = await DetectionOverride().apply("Emma", primary)
        assert result == primary


class TestWhitelist:
    async def test_adds_a_missed_value(self) -> None:
        """A whitelisted value absent from the detections is forced in."""
        override = DetectionOverride(whitelist=ExactMatchDetector({"Acme": "ORG"}))
        result = await override.apply("Acme rocks", [])
        assert len(result) == 1
        assert result[0].span == Span(0, 4)
        assert result[0].label == "ORG"
        assert result[0].confidence == 1.0

    async def test_replaces_an_overlapping_detection(self) -> None:
        """A forced detection replaces what it overlaps, the server label wins."""
        primary = [_detection(0, 8, "Emma Doe", label="COMPANY")]
        override = DetectionOverride(
            whitelist=ExactMatchDetector({"Emma Doe": "PERSON"})
        )
        result = await override.apply("Emma Doe called", primary)
        assert len(result) == 1
        assert result[0].label == "PERSON"


class TestBlacklistStrategies:
    async def test_exact_removes_the_identical_detection(self) -> None:
        """EXACT invalidates a detection with the same span and label."""
        primary = [_detection(6, 11, "Paris", label="LOCATION")]
        override = DetectionOverride(
            blacklist=ExactMatchDetector({"Paris": "LOCATION"})
        )
        assert await override.apply("Visit Paris", primary) == []

    async def test_exact_keeps_a_label_mismatch(self) -> None:
        """EXACT leaves a detection whose label differs from the blacklist's."""
        primary = [_detection(6, 11, "Paris", label="PERSON")]
        override = DetectionOverride(
            blacklist=ExactMatchDetector({"Paris": "LOCATION"})
        )
        assert await override.apply("Visit Paris", primary) == primary

    async def test_value_removes_the_value_everywhere(self) -> None:
        """VALUE invalidates every detection of the value, labels ignored."""
        primary = [
            _detection(6, 11, "Paris", label="PERSON"),
            _detection(16, 21, "Paris", label="LOCATION"),
        ]
        override = DetectionOverride(
            blacklist=ExactMatchDetector({"Paris": "LOCATION"}),
            blacklist_strategy=BlacklistStrategy.VALUE,
        )
        assert await override.apply("Visit Paris and Paris", primary) == []

    async def test_overlap_removes_what_it_touches(self) -> None:
        """OVERLAP invalidates any detection overlapping a blacklisted span."""
        primary = [_detection(6, 18, "Paris region", label="REGION")]
        override = DetectionOverride(
            blacklist=ExactMatchDetector({"Paris": "LOCATION"}),
            blacklist_strategy=BlacklistStrategy.OVERLAP,
        )
        assert await override.apply("Visit Paris region", primary) == []


class TestConflictStrategies:
    async def test_whitelist_wins_by_default(self) -> None:
        """A value on both lists is anonymized under WHITELIST_WINS."""
        override = DetectionOverride(
            whitelist=ExactMatchDetector({"Emma": "PERSON"}),
            blacklist=ExactMatchDetector({"Emma": "PERSON"}),
        )
        result = await override.apply("Hi Emma", [])
        assert len(result) == 1
        assert result[0].label == "PERSON"

    async def test_blacklist_wins_clears_the_forced_value(self) -> None:
        """Under BLACKLIST_WINS the cleared value stays clear."""
        override = DetectionOverride(
            whitelist=ExactMatchDetector({"Emma": "PERSON"}),
            blacklist=ExactMatchDetector({"Emma": "PERSON"}),
            conflict_strategy=OverrideConflictStrategy.BLACKLIST_WINS,
        )
        assert await override.apply("Hi Emma", []) == []

    async def test_raise_refuses_the_collision(self) -> None:
        """Under RAISE a span both forced and cleared is a loud error."""
        override = DetectionOverride(
            whitelist=ExactMatchDetector({"Emma": "PERSON"}),
            blacklist=ExactMatchDetector({"Emma": "LOCATION"}),
            conflict_strategy=OverrideConflictStrategy.RAISE,
        )
        with pytest.raises(ConflictingOverrideError, match="Emma"):
            await override.apply("Hi Emma", [])


class TestClearedValues:
    async def test_reports_the_blacklisted_values(self) -> None:
        """cleared_values returns the casefolded texts the blacklist matches."""
        override = DetectionOverride(
            blacklist=ExactMatchDetector({"Paris": "LOCATION"})
        )
        assert await override.cleared_values("Visit Paris") == frozenset({"paris"})

    async def test_is_empty_without_a_blacklist(self) -> None:
        """cleared_values is empty when no blacklist is configured."""
        assert await DetectionOverride().cleared_values("Visit Paris") == frozenset()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/components/override/test_override.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'piighost.components.override'`.

- [ ] **Step 3: Write the exceptions, strategies, port, and component**

In `src/piighost/exceptions.py`, at the end of the file (after `UnrecognizableFactoryError`), add:

```python
class OverrideError(PIIGhostError):
    """Base class for errors raised by a detection override.

    Catch this to handle any override failure at once, or catch one of its
    subclasses to react to a specific violation.
    """


class ConflictingOverrideError(OverrideError):
    """Raised when the whitelist and the blacklist contradict each other.

    Under the RAISE conflict strategy, a span both forced and cleared is a
    configuration error, refused loudly rather than resolved silently.
    """
```

Create `src/piighost/components/override/strategy.py`:

```python
"""Override strategies: how the blacklist invalidates and who wins a conflict."""

from enum import Enum


class BlacklistStrategy(Enum):
    """How a blacklist detection invalidates an already-detected one.

    EXACT, the default, invalidates only a detection with the identical span
    and label, the most predictable rule. VALUE invalidates every detection
    carrying the same casefolded text, positions and labels ignored, the
    classic never-anonymize-this-value list. OVERLAP invalidates any detection
    overlapping a blacklisted span, labels ignored, the most aggressive rule.
    """

    EXACT = "exact"
    VALUE = "value"
    OVERLAP = "overlap"


class OverrideConflictStrategy(Enum):
    """Who wins when the whitelist and the blacklist contradict each other.

    WHITELIST_WINS, the default, applies the blacklist to the primary
    detections first and adds the whitelist last, so a contradicted value is
    anonymized, the fail-closed reading. BLACKLIST_WINS applies the whitelist
    first and lets the blacklist invalidate the result, forced values included.
    RAISE refuses a collision between the two lists' outputs with a
    ConflictingOverrideError.
    """

    WHITELIST_WINS = "whitelist_wins"
    BLACKLIST_WINS = "blacklist_wins"
    RAISE = "raise"
```

Create `src/piighost/components/override/base.py`:

```python
"""Detection override abstractions: the port for server-imposed lists."""

from typing import Protocol, runtime_checkable

from piighost.models import Detection


@runtime_checkable
class AnyDetectionOverride(Protocol):
    """A component imposing server decisions on a detection set.

    It is applied right after detection, before overlap resolution and linking,
    and at the memory write points of the thread pipeline, so its decisions
    trump both the detector's output and a human's corrected set. There is no
    Base template: implementations would differ by their whole mechanism, not
    by a single hook, the same pairwise exception as the guard rails.
    """

    async def apply(self, text: str, detections: list[Detection]) -> list[Detection]:
        """Return the detections with the server lists imposed.

        Args:
            text: The message the detections were found in.
            detections: The detections to correct, from any origin.

        Returns:
            The corrected detections, in position order.
        """
        ...

    async def cleared_values(self, text: str) -> frozenset[str]:
        """Return the casefolded values the blacklist matches in this text.

        The pipeline exempts them from the guard rail: a blacklisted value is
        deliberately left in clear, so a detector-based guard would otherwise
        re-find it and refuse the output.

        Args:
            text: The message to scan with the blacklist.

        Returns:
            The casefolded matched values, empty without a blacklist.
        """
        ...
```

Create `src/piighost/components/override/detector.py`:

```python
"""Detector-driven override: force and clear detections by server decision."""

from collections.abc import Callable

from piighost.components.detector.base import AnyDetector
from piighost.components.override.strategy import (
    BlacklistStrategy,
    OverrideConflictStrategy,
)
from piighost.exceptions import ConflictingOverrideError
from piighost.models import Detection


def _exact_invalidated(detection: Detection, cleared: list[Detection]) -> bool:
    """Whether a cleared detection matches this one span for span, label for label."""
    return any(
        cleared_one.span == detection.span and cleared_one.label == detection.label
        for cleared_one in cleared
    )


def _value_invalidated(detection: Detection, cleared: list[Detection]) -> bool:
    """Whether any cleared detection carries this one's casefolded text."""
    values = {cleared_one.text.casefold() for cleared_one in cleared}
    return detection.text.casefold() in values


def _overlap_invalidated(detection: Detection, cleared: list[Detection]) -> bool:
    """Whether any cleared detection overlaps this one, labels ignored."""
    return any(detection.span.overlaps(cleared_one.span) for cleared_one in cleared)


_BLACKLIST_RULES: dict[
    BlacklistStrategy, Callable[[Detection, list[Detection]], bool]
] = {
    BlacklistStrategy.EXACT: _exact_invalidated,
    BlacklistStrategy.VALUE: _value_invalidated,
    BlacklistStrategy.OVERLAP: _overlap_invalidated,
}
"""One invalidation predicate per blacklist strategy."""


class DetectionOverride:
    """Force and clear detections by server decision, driven by detectors.

    The whitelist is a detector whose detections are added no matter what,
    replacing any detection they overlap, so the server's value and label win
    over the primary detector's reading. The blacklist is a detector whose
    detections invalidate existing ones, per the blacklist strategy. Because the
    pipelines apply this component after every detection read and before every
    memory write, both lists also trump a human's corrected set.

    This is the production way to force values: a whitelist built on an
    ExactMatchDetector or a RegexDetector survives HITL corrections, where
    ExactMatchDetector used alone as a primary detector is first a test helper.

    Attributes:
        whitelist: The detector whose detections are forced in, or None.
        blacklist: The detector whose detections invalidate, or None.
        blacklist_strategy: How a blacklist detection invalidates.
        conflict_strategy: Who wins when the two lists contradict each other.
    """

    def __init__(
        self,
        whitelist: AnyDetector | None = None,
        blacklist: AnyDetector | None = None,
        blacklist_strategy: BlacklistStrategy = BlacklistStrategy.EXACT,
        conflict_strategy: OverrideConflictStrategy = (
            OverrideConflictStrategy.WHITELIST_WINS
        ),
    ) -> None:
        """Store the two list detectors and their strategies."""
        self.whitelist = whitelist
        self.blacklist = blacklist
        self.blacklist_strategy = blacklist_strategy
        self.conflict_strategy = conflict_strategy

    async def apply(self, text: str, detections: list[Detection]) -> list[Detection]:
        """Return the detections with the server lists imposed.

        The conflict strategy decides the application order: WHITELIST_WINS
        clears first and forces last, BLACKLIST_WINS forces first and clears
        last, RAISE refuses any collision between the two lists' outputs before
        applying either.
        """
        forced = await self.whitelist.detect(text) if self.whitelist else []
        cleared = await self.blacklist.detect(text) if self.blacklist else []

        if self.conflict_strategy is OverrideConflictStrategy.RAISE:
            self._refuse_collisions(forced, cleared)

        if self.conflict_strategy is OverrideConflictStrategy.BLACKLIST_WINS:
            forced_first = self._force(detections, forced)
            return self._clear(forced_first, cleared)

        kept = self._clear(detections, cleared)
        return self._force(kept, forced)

    async def cleared_values(self, text: str) -> frozenset[str]:
        """Return the casefolded values the blacklist matches in this text."""
        if self.blacklist is None:
            return frozenset()
        cleared = await self.blacklist.detect(text)
        return frozenset(detection.text.casefold() for detection in cleared)

    def _force(
        self, detections: list[Detection], forced: list[Detection]
    ) -> list[Detection]:
        """Add the whitelist detections, replacing any detection they overlap."""
        if not forced:
            return detections
        kept = [
            detection
            for detection in detections
            if not any(detection.overlaps(forced_one) for forced_one in forced)
        ]
        combined = kept + list(forced)
        return sorted(combined)

    def _clear(
        self, detections: list[Detection], cleared: list[Detection]
    ) -> list[Detection]:
        """Drop the detections the blacklist invalidates, per the strategy."""
        if not cleared:
            return detections
        invalidated = _BLACKLIST_RULES[self.blacklist_strategy]
        return [
            detection for detection in detections if not invalidated(detection, cleared)
        ]

    def _refuse_collisions(
        self, forced: list[Detection], cleared: list[Detection]
    ) -> None:
        """Raise when the two lists contradict each other on a span."""
        for forced_one in forced:
            for cleared_one in cleared:
                if forced_one.span.overlaps(cleared_one.span):
                    raise ConflictingOverrideError(
                        f"Overrides contradict each other on '{forced_one.text}': "
                        "a whitelisted span overlaps a blacklisted one."
                    )
```

Create `src/piighost/components/override/__init__.py`:

```python
"""Detection overrides: server lists that trump detection and user feedback.

base.py holds the AnyDetectionOverride port, strategy.py the blacklist and
conflict strategies, and DetectionOverride is the detector-driven
implementation. The package is pure, so everything is exported eagerly.
"""

from piighost.components.override.base import AnyDetectionOverride
from piighost.components.override.detector import DetectionOverride
from piighost.components.override.strategy import (
    BlacklistStrategy,
    OverrideConflictStrategy,
)

__all__ = [
    "AnyDetectionOverride",
    "BlacklistStrategy",
    "DetectionOverride",
    "OverrideConflictStrategy",
]
```

- [ ] **Step 4: Run it to verify it passes**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/components/override/test_override.py -q`
Expected: PASS, 13 passed.

- [ ] **Step 5: Lint and types, then commit**

Run: `uv run --no-sync ruff format src/piighost tests/components/override && uv run --no-sync ruff check src/piighost tests/components/override && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean, pyrefly 0 errors.

```bash
git add src/piighost/exceptions.py src/piighost/components/override tests/components/override/test_override.py
git commit -m "feat(override): add the detection override component"
```

---

### Task 2: Base pipeline integration

**Files:**
- Modify: `src/piighost/pipeline/base.py`
- Modify: `tests/observation/test_pipeline_spans.py`
- Test: `tests/pipeline/test_override_integration.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/pipeline/test_override_integration.py`:

```python
"""Integration tests for the override stage in both pipelines."""

import pytest

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.guard import DetectorGuardRail
from piighost.components.linker import ExactEntityLinker
from piighost.components.override import BlacklistStrategy, DetectionOverride
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.exceptions import PIIRemainingError
from piighost.pipeline import AnonymizationPipeline


def _pipeline(
    detector: ExactMatchDetector,
    override: DetectionOverride,
    guard: DetectorGuardRail | None = None,
) -> AnonymizationPipeline:
    """Build a base pipeline with an override and an optional guard."""
    return AnonymizationPipeline(
        detector,
        ExactEntityLinker(),
        Anonymizer(LabelCounterPlaceholderFactory()),
        guard=guard,
        override=override,
    )


class TestBasePipelineOverride:
    async def test_whitelist_forces_a_value_the_detector_missed(self) -> None:
        """A whitelisted value is anonymized though the detector never saw it."""
        override = DetectionOverride(whitelist=ExactMatchDetector({"Acme": "ORG"}))
        pipeline = _pipeline(ExactMatchDetector({}), override)
        result = await pipeline.anonymize("Acme rocks")
        assert result.text == "<<ORG:1>> rocks"

    async def test_blacklist_keeps_a_false_positive_in_clear(self) -> None:
        """A blacklisted value the detector flags stays in clear."""
        override = DetectionOverride(
            blacklist=ExactMatchDetector({"Paris": "LOCATION"})
        )
        pipeline = _pipeline(ExactMatchDetector({"Paris": "LOCATION"}), override)
        result = await pipeline.anonymize("Visit Paris")
        assert result.text == "Visit Paris"

    async def test_blacklisted_value_does_not_trip_the_guard(self) -> None:
        """A guard that knows the blacklisted value exempts it, by design."""
        override = DetectionOverride(
            blacklist=ExactMatchDetector({"Paris": "LOCATION"}),
            blacklist_strategy=BlacklistStrategy.VALUE,
        )
        guard = DetectorGuardRail(ExactMatchDetector({"Paris": "LOCATION"}))
        pipeline = _pipeline(ExactMatchDetector({"Emma": "PERSON"}), override, guard)
        result = await pipeline.anonymize("Emma visits Paris")
        assert result.text == "<<PERSON:1>> visits Paris"

    async def test_a_real_leak_still_trips_the_guard(self) -> None:
        """The exemption covers the blacklist only, other leaks still refuse."""
        override = DetectionOverride(
            blacklist=ExactMatchDetector({"Paris": "LOCATION"})
        )
        guard = DetectorGuardRail(ExactMatchDetector({"leak@x.com": "EMAIL"}))
        pipeline = _pipeline(ExactMatchDetector({"Emma": "PERSON"}), override, guard)
        with pytest.raises(PIIRemainingError):
            await pipeline.anonymize("Emma wrote leak@x.com")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/pipeline/test_override_integration.py -q`
Expected: FAIL with `TypeError` (`override` is not an accepted parameter).

- [ ] **Step 3: Integrate the stage into the base pipeline**

In `src/piighost/pipeline/base.py`:

Add the import (with the other component imports, sorted):

```python
from piighost.components.override.base import AnyDetectionOverride
```

Extend `BaseAnonymizationPipeline.__init__` with a new LAST parameter and attribute (docstring gains one sentence):

```python
        observation_redactor: AnyPlaceholderFactory | None = None,
        override: AnyDetectionOverride | None = None,
```

with, in the body, after `self.observation_redactor = ...`:

```python
        self.override = override
```

and, appended to the `__init__` docstring:

```python
        override imposes the server's whitelist and blacklist on every
        detection set, trumping the detector and any corrected set.
```

Also add `override` to the class docstring's Attributes section:

```python
        override: The server override imposed on every detection set, or None.
```

Add two helpers after `_resolve_entities`:

```python
    async def _override(
        self, text: str, detections: list[Detection]
    ) -> list[Detection]:
        """Impose the override, or pass detections through when disabled."""
        if self.override is None:
            return detections
        return await self.override.apply(text, detections)

    async def _cleared_values(self, text: str) -> frozenset[str]:
        """The values the blacklist clears here, exempted from the guard.

        A blacklisted value is deliberately left in clear, so a detector-based
        guard would re-find it and refuse the output. Empty when no override or
        no guard is configured, since the exemption only serves the guard.
        """
        if self.override is None or self.guard is None:
            return frozenset()
        return await self.override.cleared_values(text)
```

In `AnonymizationPipeline.anonymize`, insert the override stage between the detect span and the overlap stage, move `root.set_input` AFTER the override (so a redacted input payload covers forced values too), and feed the guard's expected set. The method becomes:

```python
    async def anonymize(self, text: str) -> Anonymization[PreservationT]:
        """Return the anonymized text and token mapping for the given text.

        Raises:
            PIIRemainingError: If a guard flags PII left in the output.
        """
        with self._tracer.span("piighost.anonymize") as root:
            with self._tracer.span("piighost.detect") as span:
                detections = await self.detector.detect(text)
                span.set_attribute("count", len(detections))
                span.set_output(self._payload_detections(detections))

            with self._stage_span("piighost.override", self.override):
                detections = await self._override(text, detections)
            root.set_input(self._payload_text(text, detections))

            with self._stage_span("piighost.overlap", self.overlap_resolver):
                detections = self._resolve_overlaps(detections)
            with self._stage_span("piighost.expand", self.expander):
                detections = self._expand(text, detections)

            with self._tracer.span("piighost.link") as span:
                entities = self._link(detections)
                span.set_output(self._payload_entities(entities))

            with self._stage_span("piighost.entity_resolve", self.entity_resolver):
                entities = self._resolve_entities(entities)

            with self._tracer.span("piighost.render") as span:
                result = self.anonymizer.anonymize(text, entities)
                span.set_attribute("tokens", len(result.tokens))
                span.set_output(result.text)

            with self._stage_span("piighost.guard", self.guard) as span:
                cleared = await self._cleared_values(text)
                verdict = await self._guard(result.text, cleared)
                if verdict is not None:
                    labels = sorted({d.label for d in verdict.detections})
                    span.set_output({"flagged": verdict.flagged, "labels": labels})

            root.set_output(result.text)
            return result
```

In `tests/observation/test_pipeline_spans.py`, extend `test_optional_stage_spans_appear_when_configured` to cover the override span. The test becomes:

```python
    async def test_optional_stage_spans_appear_when_configured(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Configured optional stages get spans; disabled ones never do."""
        pipeline = _pipeline(
            overlap_resolver=ConfidenceOverlapResolver(),
            guard=DetectorGuardRail(ExactMatchDetector({})),
            override=DetectionOverride(whitelist=ExactMatchDetector({"Liam": "PERSON"})),
        )
        await pipeline.anonymize("Hi Emma!")
        names = [span.name for span in exporter.get_finished_spans()]
        assert "piighost.override" in names
        assert "piighost.overlap" in names
        assert "piighost.guard" in names
        assert "piighost.expand" not in names
        assert "piighost.entity_resolve" not in names
        assert names.index("piighost.detect") < names.index("piighost.override")
        assert names.index("piighost.override") < names.index("piighost.link")
```

with the import added to that file's import block:

```python
from piighost.components.override import DetectionOverride
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/pipeline/test_override_integration.py tests/observation/ -q`
Expected: PASS (4 new integration tests plus the observation suite).

- [ ] **Step 5: Run the full suite, lint, and types**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest -q`
Expected: PASS, no regressions.

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean, pyrefly 0 errors.

- [ ] **Step 6: Commit**

```bash
git add src/piighost/pipeline/base.py tests/pipeline/test_override_integration.py tests/observation/test_pipeline_spans.py
git commit -m "feat(pipeline): impose detection overrides in the base pipeline"
```

---

### Task 3: Thread pipeline integration

**Files:**
- Modify: `src/piighost/pipeline/thread.py`
- Test: `tests/pipeline/test_override_integration.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `tests/pipeline/test_override_integration.py`:

```python
class TestThreadPipelineOverride:
    async def test_whitelist_trumps_a_hitl_drop(self) -> None:
        """A correction removing a whitelisted value sees it re-imposed."""
        override = DetectionOverride(whitelist=ExactMatchDetector({"Emma": "PERSON"}))
        pipeline = ThreadAnonymizationPipeline(
            ExactMatchDetector({}),
            ExactEntityLinker(),
            Anonymizer(LabelCounterPlaceholderFactory()),
            InMemoryConversationMemory(),
            override=override,
        )
        result = await pipeline.anonymize_corrected("Hi Emma", "t1", [])
        assert result.text == "Hi <<PERSON:1>>"

    async def test_blacklist_trumps_a_hitl_add(self) -> None:
        """A correction adding a blacklisted value sees it cleared."""
        override = DetectionOverride(
            blacklist=ExactMatchDetector({"Paris": "LOCATION"})
        )
        pipeline = ThreadAnonymizationPipeline(
            ExactMatchDetector({}),
            ExactEntityLinker(),
            Anonymizer(LabelCounterPlaceholderFactory()),
            InMemoryConversationMemory(),
            override=override,
        )
        added = Detection(
            span=Span(6, 11),
            text="Paris",
            label="LOCATION",
            confidence=1.0,
        )
        result = await pipeline.anonymize_corrected("Visit Paris", "t1", [added])
        assert result.text == "Visit Paris"

    async def test_whitelisted_value_is_deanonymizable(self) -> None:
        """A forced value enters the thread token map and restores."""
        override = DetectionOverride(whitelist=ExactMatchDetector({"Emma": "PERSON"}))
        pipeline = ThreadAnonymizationPipeline(
            ExactMatchDetector({}),
            ExactEntityLinker(),
            Anonymizer(LabelCounterPlaceholderFactory()),
            InMemoryConversationMemory(),
            override=override,
        )
        await pipeline.anonymize("Hi Emma", "t1")
        restored = await pipeline.deanonymize("<<PERSON:1>>", "t1")
        assert restored == "Emma"
```

with these imports added to the file's import block:

```python
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.models import Detection, Span
from piighost.pipeline import ThreadAnonymizationPipeline
```

- [ ] **Step 2: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/pipeline/test_override_integration.py -q`
Expected: the three thread tests FAIL (`TypeError`: `override` not accepted).

- [ ] **Step 3: Integrate the write points into the thread pipeline**

In `src/piighost/pipeline/thread.py`:

Add the import (sorted):

```python
from piighost.components.override.base import AnyDetectionOverride
```

Extend the constructor with the new LAST parameter, forwarded positionally to super (after `observation_redactor`):

```python
        observation_redactor: AnyPlaceholderFactory | None = None,
        override: AnyDetectionOverride | None = None,
    ) -> None:
        """Store the stage components and the per-thread conversation memory."""
        super().__init__(
            detector,
            linker,
            anonymizer,
            overlap_resolver,
            expander,
            entity_resolver,
            guard,
            observation_redactor,
            override,
        )
        self.memory = memory
```

In `_detect`, impose the override on the fresh path between detection and overlap resolution, so the memory stores the post-override set (the override span nests under the detect span there, which is honest, that is when it runs):

```python
        detections = await self.detector.detect(text)
        with self._stage_span("piighost.override", self.override):
            detections = await self._override(text, detections)
        detections = self._resolve_overlaps(detections)
        detections = self._expand(text, detections)
```

In `anonymize`, feed the guard's expected set with the blacklist exemption. The guard block becomes:

```python
            with self._stage_span("piighost.guard", self.guard) as span:
                cleared = await self._cleared_values(text)
                verdict = await self._guard(rendered, preserved | cleared)
                if verdict is not None:
                    labels = sorted({d.label for d in verdict.detections})
                    span.set_output({"flagged": verdict.flagged, "labels": labels})
```

In `anonymize_corrected`, impose the override on the corrected set before it is stored. The body becomes:

```python
        corrected = await self._override(text, detections)
        await self.memory.remember(
            thread_id=thread_id,
            message=text,
            detections=corrected,
            role=MessageRole.USER,
        )
        return await self.anonymize(text, thread_id, MessageRole.USER)
```

and its docstring gains one sentence, after "the human is authoritative over it.":

```python
        Server-side overrides are the one exception: the corrected set passes
        through the configured override before it is stored, so the server's
        lists trump the correction.
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/pipeline/ -q`
Expected: PASS (the 7 override integration tests plus the existing pipeline, thread, and HITL suites).

- [ ] **Step 5: Run the full suite, lint, and types**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest -q`
Expected: PASS.

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean, pyrefly 0 errors.

- [ ] **Step 6: Commit**

```bash
git add src/piighost/pipeline/thread.py tests/pipeline/test_override_integration.py
git commit -m "feat(pipeline): impose detection overrides across the thread"
```

---

### Task 4: Public-API regression and full verification

**Files:**
- Modify: `tests/regression/test_imports.py`

- [ ] **Step 1: Add the override symbols to the regression guard**

In `tests/regression/test_imports.py`, in the `PUBLIC_API` list, after the last `("piighost.components.guard", ...)` line, add:

```python
    ("piighost.components.override", "AnyDetectionOverride"),
    ("piighost.components.override", "BlacklistStrategy"),
    ("piighost.components.override", "DetectionOverride"),
    ("piighost.components.override", "OverrideConflictStrategy"),
```

and, after the `("piighost.exceptions", "UnrecognizableFactoryError"),` line:

```python
    ("piighost.exceptions", "OverrideError"),
    ("piighost.exceptions", "ConflictingOverrideError"),
```

- [ ] **Step 2: Run the regression guard, the full suite, and the checks**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/regression/test_imports.py -q`
Expected: PASS with the six new cases.

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest -q`
Expected: PASS.

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean, pyrefly 0 errors.

- [ ] **Step 3: Commit**

```bash
git add tests/regression/test_imports.py
git commit -m "test(override): guard the override public symbols"
```

---

## Notes for the implementer

- The precedence chain is the point of this design: server overrides, then HITL corrections, then automatic detection. It is realized by applying the override at every read of fresh detections AND at every memory write (fresh `_detect` path, `anonymize_corrected`), never only in the detector stage. Do not "optimize" an application point away.
- The base pipeline's `root.set_input` deliberately moves AFTER the override stage, so a redacted observation payload covers forced values.
- Known interaction, documented in the spec, not to fix here: with `BlacklistStrategy.EXACT` and an expander configured, the expander can re-add a span the blacklist invalidated. The spec recommends VALUE with an expander.
- Known trade-off, documented: server list changes do not re-apply to already-cached messages (resend or `forget_thread`).
- The component is pure (no optional dependency): eager imports and exports, symbols in `PUBLIC_API`.
- `_pii_remaining`, `_guard`, and the observation helpers in `pipeline/base.py` are NOT modified; only `anonymize`, `__init__`, and the two new helpers change.
