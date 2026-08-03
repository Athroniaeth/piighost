# Regex Detector and Pattern Catalogs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a pure-Python `RegexDetector`, four reusable regex pattern catalogs, and a `CompositeDetector`, all covered by unit and golden tests, with no optional dependency.

**Architecture:** Three adapters of the existing `AnyDetector` port under `src/piighost/components/detector/`. `RegexDetector` compiles a `{label: pattern}` dict and emits one `Detection` per non-overlapping match at confidence 1.0. Catalogs live in a `patterns/` sub-package as plain dicts. `CompositeDetector` fans out to child detectors via `asyncio.gather` and concatenates results. No checksum validators (an OCR-mangled value must be kept, not dropped, or it leaks).

**Tech Stack:** Python 3.11+, `re`, `asyncio`, pytest (`asyncio_mode = "auto"`, so async tests need no decorator).

---

## Conventions for every task

- Run tests with `uv run --no-sync pytest ...`. Before each run, clear stale bytecode: `find src tests -name __pycache__ -type d -exec rm -rf {} +`.
- The `Detection` model is a frozen dataclass with fields `span: Span`, `text: str`, `label: str`, `confidence: float`. `Span(start, end)` is a half-open range and rejects `end <= start`. Build detections as `Detection(span=Span(a, b), text=..., label=..., confidence=1.0)`.
- Docstrings are plain prose plus bullet lists only, no markdown or RST markup (no `::`, no `:class:`). Code artifacts stay in English.
- No `from __future__ import annotations`; use native 3.11+ typing (`dict[str, str]`, `list[Detection]`).
- Commit with Conventional Commits.

## File structure

- Create `src/piighost/components/detector/regex.py` — `RegexDetector` (Task 1).
- Create `src/piighost/components/detector/patterns/__init__.py`, `generic.py`, `us.py`, `eu.py`, `fr.py` — catalog dicts (Task 2).
- Create `src/piighost/components/detector/composite.py` — `CompositeDetector` (Task 3).
- Modify `src/piighost/components/detector/__init__.py` — public exports (Tasks 1 and 3).
- Modify `tests/regression/test_imports.py` — public-symbol regression (Task 4).
- Create `tests/components/detector/test_regex.py`, `test_patterns.py`, `test_composite.py`.

---

### Task 1: RegexDetector

**Files:**
- Create: `src/piighost/components/detector/regex.py`
- Modify: `src/piighost/components/detector/__init__.py`
- Test: `tests/components/detector/test_regex.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/components/detector/test_regex.py`:

```python
"""Tests for the RegexDetector."""

from piighost.components.detector import AnyDetector, RegexDetector
from piighost.models import Span


class TestConformance:
    def test_satisfies_the_detector_port(self) -> None:
        """RegexDetector is an AnyDetector."""
        assert isinstance(RegexDetector({}), AnyDetector)


class TestDetect:
    async def test_finds_a_single_match_with_exact_offsets(self) -> None:
        """A pattern matching once yields one detection at the right span."""
        detector = RegexDetector({"DIGITS": r"\d+"})
        detections = await detector.detect("id 4242 ok")
        assert len(detections) == 1
        assert detections[0].span == Span(3, 7)
        assert detections[0].text == "4242"
        assert detections[0].label == "DIGITS"
        assert detections[0].confidence == 1.0

    async def test_finds_every_match_of_a_pattern(self) -> None:
        """A pattern matching several times yields one detection each."""
        detector = RegexDetector({"DIGITS": r"\d+"})
        detections = await detector.detect("1 and 22 and 333")
        spans = [detection.span for detection in detections]
        assert spans == [Span(0, 1), Span(6, 8), Span(13, 16)]

    async def test_finds_matches_for_every_label(self) -> None:
        """Each configured pattern contributes its own labeled detections."""
        detector = RegexDetector({"DIGITS": r"\d+", "WORD": r"[A-Za-z]+"})
        detections = await detector.detect("ab 12")
        found = {(detection.text, detection.label) for detection in detections}
        assert found == {("ab", "WORD"), ("12", "DIGITS")}

    async def test_empty_text_returns_empty(self) -> None:
        """Scanning empty text yields no detection."""
        detector = RegexDetector({"DIGITS": r"\d+"})
        assert await detector.detect("") == []

    async def test_no_match_returns_empty(self) -> None:
        """A text matching no pattern yields no detection."""
        detector = RegexDetector({"DIGITS": r"\d+"})
        assert await detector.detect("no numbers here") == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/components/detector/test_regex.py -q`
Expected: FAIL with `ImportError: cannot import name 'RegexDetector'`.

- [ ] **Step 3: Write the implementation**

Create `src/piighost/components/detector/regex.py`:

```python
"""Regex detector: find PII by matching configured patterns, one per label."""

import re

from piighost.models import Detection, Span


class RegexDetector:
    """Detector that finds PII by matching regex patterns, one per label.

    Each pattern is compiled once at construction. detect emits one detection
    per non-overlapping match, at a flat confidence of 1.0. It carries no
    checksum validator and no optional dependency, so it stays cheap and matches
    on shape alone. A structured value mangled by OCR is kept rather than
    dropped, because dropping a real value would leak it.

    Attributes:
        patterns: Mapping of PII label to the regex pattern string to match.
    """

    def __init__(self, patterns: dict[str, str]) -> None:
        """Compile every configured pattern, keyed by its label."""
        self.patterns = patterns
        self._compiled: dict[str, re.Pattern[str]] = {
            label: re.compile(pattern) for label, pattern in patterns.items()
        }

    async def detect(self, text: str) -> list[Detection]:
        """Return one detection per non-overlapping match of each pattern."""
        detections: list[Detection] = []
        for label, compiled in self._compiled.items():
            for match in compiled.finditer(text):
                span = Span(match.start(), match.end())
                detection = Detection(
                    span=span,
                    text=match.group(),
                    label=label,
                    confidence=1.0,
                )
                detections.append(detection)
        return detections
```

Modify `src/piighost/components/detector/__init__.py` to export it. The full file becomes:

```python
"""Detectors: components that find PII in text.

AnyDetector defines the port; each module provides an adapter.
"""

from piighost.components.detector.base import AnyDetector
from piighost.components.detector.chunked import ChunkedDetector
from piighost.components.detector.exact import ExactMatchDetector
from piighost.components.detector.regex import RegexDetector

__all__ = [
    "AnyDetector",
    "ChunkedDetector",
    "ExactMatchDetector",
    "RegexDetector",
]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/components/detector/test_regex.py -q`
Expected: PASS, 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/piighost/components/detector/regex.py src/piighost/components/detector/__init__.py tests/components/detector/test_regex.py
git commit -m "feat(detector): add a regex detector"
```

---

### Task 2: Pattern catalogs

**Files:**
- Create: `src/piighost/components/detector/patterns/__init__.py`
- Create: `src/piighost/components/detector/patterns/generic.py`
- Create: `src/piighost/components/detector/patterns/us.py`
- Create: `src/piighost/components/detector/patterns/eu.py`
- Create: `src/piighost/components/detector/patterns/fr.py`
- Test: `tests/components/detector/test_patterns.py`

The `URL` and `US_PHONE` patterns below are corrected versions of their v1 form (see the spec's resilience section). The corrected values are exactly what the tests assert, so use them verbatim.

- [ ] **Step 1: Write the failing golden tests**

Create `tests/components/detector/test_patterns.py`:

```python
"""Golden tests for the regex pattern catalogs.

Each pattern is checked against known true positives that must match in full
and true negatives that must not match. Resilience cases wrap a value in
adjacent punctuation and assert the detection covers the value alone, with the
trailing punctuation excluded.
"""

import pytest

from piighost.components.detector import RegexDetector
from piighost.components.detector.patterns import (
    EU_PATTERNS,
    FR_PATTERNS,
    GENERIC_PATTERNS,
    US_PATTERNS,
)

ALL_PATTERNS: dict[str, str] = {
    **GENERIC_PATTERNS,
    **US_PATTERNS,
    **EU_PATTERNS,
    **FR_PATTERNS,
}

TRUE_POSITIVES: list[tuple[str, str]] = [
    ("EMAIL", "john.doe@example.com"),
    ("URL", "https://example.com/path?q=1"),
    ("IPV4", "192.168.0.1"),
    ("CREDIT_CARD", "4111 1111 1111 1111"),
    ("US_SSN", "123-45-6789"),
    ("US_PHONE", "+1 (415) 555-2671"),
    ("US_PHONE", "415-555-2671"),
    ("US_ZIP", "94103-1234"),
    ("US_ZIP", "94103"),
    ("IBAN", "GB82WEST12345698765432"),
    ("FR_PHONE", "+33612345678"),
    ("FR_PHONE", "06 12 34 56 78"),
    ("FR_IBAN", "FR7630006000011234567890189"),
    ("FR_NIR", "180057505600157"),
    ("FR_SIRET", "73282932000074"),
]

TRUE_NEGATIVES: list[tuple[str, str]] = [
    ("EMAIL", "not an email"),
    ("EMAIL", "john@doe"),
    ("IPV4", "999.999.999.999"),
    ("US_SSN", "1234-56-789"),
    ("FR_PHONE", "0012345678"),
]

# label, value, wrapper template with {v} where the value goes.
RESILIENCE_WRAPPERS: list[str] = [
    "{v}.",
    "{v},",
    "{v}\n",
    " {v} ",
    "({v})",
    "Reach me at {v}.",
]

RESILIENCE_VALUES: list[tuple[str, str]] = [
    ("EMAIL", "john.doe@example.com"),
    ("URL", "https://example.com/path?q=1"),
    ("IPV4", "192.168.0.1"),
    ("US_PHONE", "+1 (415) 555-2671"),
    ("FR_PHONE", "+33612345678"),
    ("IBAN", "GB82WEST12345698765432"),
]


async def _detect(label: str, text: str) -> list:
    """Run a single-label RegexDetector over text and return its detections."""
    detector = RegexDetector({label: ALL_PATTERNS[label]})
    return await detector.detect(text)


class TestTruePositives:
    @pytest.mark.parametrize(("label", "value"), TRUE_POSITIVES)
    async def test_pattern_matches_the_whole_value(
        self, label: str, value: str
    ) -> None:
        """The pattern matches a known instance, covering the full value."""
        detections = await _detect(label, value)
        assert any(detection.text == value for detection in detections)


class TestTrueNegatives:
    @pytest.mark.parametrize(("label", "value"), TRUE_NEGATIVES)
    async def test_pattern_rejects_a_non_instance(
        self, label: str, value: str
    ) -> None:
        """The pattern does not match a value that is not a real instance."""
        assert await _detect(label, value) == []


class TestResilience:
    @pytest.mark.parametrize(("label", "value"), RESILIENCE_VALUES)
    @pytest.mark.parametrize("wrapper", RESILIENCE_WRAPPERS)
    async def test_adjacent_punctuation_is_excluded(
        self, label: str, value: str, wrapper: str
    ) -> None:
        """A value wrapped in punctuation is detected without the punctuation."""
        text = wrapper.format(v=value)
        detections = await _detect(label, text)
        assert len(detections) == 1
        assert detections[0].text == value
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/components/detector/test_patterns.py -q`
Expected: FAIL with `ImportError` on `piighost.components.detector.patterns`.

- [ ] **Step 3: Write the catalog modules**

Create `src/piighost/components/detector/patterns/generic.py`:

```python
"""Country-agnostic PII regex patterns.

These target PII whose syntax is not country-specific, such as email, URL,
IPv4, and credit card. Pass them to a RegexDetector. Patterns match on shape
alone, with no checksum validation, so a value mangled by OCR is kept rather
than dropped.
"""

GENERIC_PATTERNS: dict[str, str] = {
    # Simplified RFC 5322, tight enough to avoid matching everything with an "@".
    "EMAIL": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    # Plain http(s) URL. The final character class excludes trailing sentence
    # punctuation, so a URL ending a sentence does not swallow the "." or ",".
    "URL": r"https?://[^\s<>\"']*[^\s<>\"'.,;:!?)\]]",
    # IPv4 with a per-octet 0-255 constraint.
    "IPV4": (
        r"(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
        r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)"
    ),
    # 13 to 19 digits with optional spaces or dashes. Matches on shape alone.
    "CREDIT_CARD": r"\b(?:\d[ -]?){12,18}\d\b",
}
```

Create `src/piighost/components/detector/patterns/us.py`:

```python
"""US PII regex patterns.

Labels are prefixed with US_ so they do not collide with other packs. Pass them
to a RegexDetector.
"""

US_PATTERNS: dict[str, str] = {
    # SSN as NNN-NN-NNNN. Does not enforce SSA invalid ranges.
    "US_SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    # US phone, optional +1 prefix, optional parentheses, then 3-3-4 digits. The
    # (?<![\w+]) lookbehind anchors before a leading "+" or "(", which a plain
    # \b would miss, and (?!\d) stops a trailing digit run from extending it.
    "US_PHONE": (
        r"(?<![\w+])(?:\+?1[\s.-]?)?\(?[2-9]\d{2}\)?"
        r"[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"
    ),
    # ZIP (5 digits) and ZIP+4 (5-4 digits).
    "US_ZIP": r"\b\d{5}(?:-\d{4})?\b",
}
```

Create `src/piighost/components/detector/patterns/eu.py`:

```python
"""Pan-European PII regex patterns.

Targets values standardised across EU member states, such as the ISO 13616
IBAN. For country-specific numbers use the per-country packs instead. Pass them
to a RegexDetector.
"""

EU_PATTERNS: dict[str, str] = {
    # Generic IBAN, 2-letter country, 2 check digits, 11 to 30 alphanumerics.
    "IBAN": r"\b[A-Z]{2}\d{2}(?:[\s-]?[A-Z0-9]){11,30}\b",
}
```

Create `src/piighost/components/detector/patterns/fr.py`:

```python
"""French PII regex patterns.

Labels are prefixed with FR_ so they do not collide with US or pan-EU packs.
Pass them to a RegexDetector. The IBAN and NIR patterns match on structure
alone, with no checksum validation.
"""

FR_PATTERNS: dict[str, str] = {
    # +33 or 0 prefix, 1-digit area code, then four pairs. Uses (?<!\d) and
    # (?!\d) because \b does not match between a non-word char and "+".
    "FR_PHONE": r"(?<!\d)(?:\+33|0)[1-9](?:[\s.-]?\d{2}){4}(?!\d)",
    # IBAN FR, FR + 2 check digits + 23 alphanumerics, optional separators.
    "FR_IBAN": r"\bFR\d{2}(?:[\s-]?[A-Z0-9]){23}\b",
    # NIR, sex + YY + MM + department + commune + order + key.
    "FR_NIR": (
        r"\b[12][\s.-]?\d{2}[\s.-]?(?:0[1-9]|1[0-2])[\s.-]?"
        r"(?:2A|2B|\d{2})[\s.-]?\d{3}[\s.-]?\d{3}[\s.-]?\d{2}\b"
    ),
    # SIRET, 9-digit SIREN + 5-digit establishment number, optional grouping.
    "FR_SIRET": r"\b\d{3}[\s-]?\d{3}[\s-]?\d{3}[\s-]?\d{5}\b",
}
```

Create `src/piighost/components/detector/patterns/__init__.py`:

```python
"""Reusable regex pattern catalogs for the RegexDetector.

Each catalog is a plain dict mapping a PII label to a regex pattern string.
Combine catalogs by dict merge, for example {**GENERIC_PATTERNS, **FR_PATTERNS}.
"""

from piighost.components.detector.patterns.eu import EU_PATTERNS
from piighost.components.detector.patterns.fr import FR_PATTERNS
from piighost.components.detector.patterns.generic import GENERIC_PATTERNS
from piighost.components.detector.patterns.us import US_PATTERNS

__all__ = ["EU_PATTERNS", "FR_PATTERNS", "GENERIC_PATTERNS", "US_PATTERNS"]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/components/detector/test_patterns.py -q`
Expected: PASS. All true-positive, true-negative, and resilience cases green.

- [ ] **Step 5: Commit**

```bash
git add src/piighost/components/detector/patterns tests/components/detector/test_patterns.py
git commit -m "feat(detector): add reusable regex pattern catalogs"
```

---

### Task 3: CompositeDetector

**Files:**
- Create: `src/piighost/components/detector/composite.py`
- Modify: `src/piighost/components/detector/__init__.py`
- Test: `tests/components/detector/test_composite.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/components/detector/test_composite.py`:

```python
"""Tests for the CompositeDetector."""

import asyncio

from piighost.components.detector import (
    AnyDetector,
    CompositeDetector,
    ExactMatchDetector,
)


class TestConformance:
    def test_satisfies_the_detector_port(self) -> None:
        """CompositeDetector is an AnyDetector."""
        assert isinstance(CompositeDetector([]), AnyDetector)


class TestDetect:
    async def test_merges_children_in_order(self) -> None:
        """Detections are concatenated in child-detector order."""
        composite = CompositeDetector(
            [
                ExactMatchDetector({"Emma": "PERSON"}),
                ExactMatchDetector({"Paris": "LOCATION"}),
            ]
        )
        detections = await composite.detect("Emma in Paris")
        labels = [detection.label for detection in detections]
        assert labels == ["PERSON", "LOCATION"]

    async def test_empty_detector_list_returns_empty(self) -> None:
        """A composite with no child returns no detection."""
        assert await CompositeDetector([]).detect("Emma in Paris") == []

    async def test_runs_children_concurrently(self) -> None:
        """Children are awaited concurrently, not strictly one after another."""
        both_started = asyncio.Event()
        started = 0

        class _Blocking:
            async def detect(self, text: str) -> list:
                nonlocal started
                started += 1
                if started == 2:
                    both_started.set()
                await both_started.wait()
                return []

        composite = CompositeDetector([_Blocking(), _Blocking()])
        # If the children ran sequentially the first would wait forever, since
        # the event is only set once both have started. gather lets both start.
        await asyncio.wait_for(composite.detect("x"), timeout=1.0)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/components/detector/test_composite.py -q`
Expected: FAIL with `ImportError: cannot import name 'CompositeDetector'`.

- [ ] **Step 3: Write the implementation**

Create `src/piighost/components/detector/composite.py`:

```python
"""Composite detector: run several detectors and merge their detections."""

import asyncio

from piighost.components.detector.base import AnyDetector
from piighost.models import Detection


class CompositeDetector:
    """Run several detectors over the same text and merge their detections.

    A detector that is itself an AnyDetector, so it composes with the pipeline
    unchanged. It runs every child concurrently and concatenates their results
    in child order. It does not deduplicate. Overlaps and duplicates flow to the
    span-conflict stage, matching the AnyDetector contract.
    """

    def __init__(self, detectors: list[AnyDetector]) -> None:
        """Store the child detectors to run, in order."""
        self._detectors = detectors

    async def detect(self, text: str) -> list[Detection]:
        """Run every child concurrently and concatenate detections in order."""
        if not self._detectors:
            return []
        results = await asyncio.gather(
            *(detector.detect(text) for detector in self._detectors)
        )
        return [detection for result in results for detection in result]
```

Modify `src/piighost/components/detector/__init__.py` to export it. The full file becomes:

```python
"""Detectors: components that find PII in text.

AnyDetector defines the port; each module provides an adapter.
"""

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
    "RegexDetector",
]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/components/detector/test_composite.py -q`
Expected: PASS, 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/piighost/components/detector/composite.py src/piighost/components/detector/__init__.py tests/components/detector/test_composite.py
git commit -m "feat(detector): add a composite detector"
```

---

### Task 4: Public-API regression and full verification

**Files:**
- Modify: `tests/regression/test_imports.py`

- [ ] **Step 1: Add the new public symbols to the regression guard**

In `tests/regression/test_imports.py`, in the `PUBLIC_API` list, after the line `("piighost.components.detector", "ChunkedDetector"),` add:

```python
    ("piighost.components.detector", "RegexDetector"),
    ("piighost.components.detector", "CompositeDetector"),
    ("piighost.components.detector.patterns", "GENERIC_PATTERNS"),
    ("piighost.components.detector.patterns", "US_PATTERNS"),
    ("piighost.components.detector.patterns", "EU_PATTERNS"),
    ("piighost.components.detector.patterns", "FR_PATTERNS"),
```

- [ ] **Step 2: Run the regression guard to verify it passes**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/regression/test_imports.py -q`
Expected: PASS. The new parametrized cases resolve each symbol.

- [ ] **Step 3: Run the full suite**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest -q`
Expected: PASS, no regressions.

- [ ] **Step 4: Run lint and type checks**

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean, pyrefly reports 0 errors under `src/piighost`.

- [ ] **Step 5: Commit**

```bash
git add tests/regression/test_imports.py
git commit -m "test(detector): guard the new detector public symbols"
```

---

## Notes for the implementer

- The `URL` and `US_PHONE` regex strings in Task 2 are deliberately different from their v1 originals; they carry the resilience fixes. Do not "restore" the v1 versions.
- Because `asyncio_mode = "auto"`, every `async def test_...` runs without a decorator. Do not add `@pytest.mark.asyncio`.
- Confidence is a flat `1.0` for every regex match; there is no scoring in this block.
- No config models or builders here; wiring these detectors into the TOML config is a later block.
