# PIIGhost Core Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the three confirmed core bugs (cross-message placeholder collision, missing word boundaries, hard pydantic dependency) and land the validated design improvements: cache-backed conversation memory, deduplicated pipeline stages, token-aware guard, forget API, complete TOML configs, hardened data model.

**Architecture:** Placeholder identity becomes a consequence of *first-seen ordering* persisted in a cache-backed `ConversationMemory` (write-through, hydrate-on-entry), instead of position-sorted lists renumbered per call. The duplicated `_anonymize_with_span` collapses into one template method in the base pipeline with three overridable hooks (`_link_stage`, `_record_entities`, `_render_stage`). Config coupling is inverted: core modules lose their bottom `X.Config = ...` imports; dispatch lives only in `config/builders.py`.

**Tech Stack:** Python 3.10+, uv, pytest (asyncio_mode=auto), ruff, pyrefly, aiocache, pydantic v2 (optional extra).

**Validated reproductions this plan must fix (from review session):**
1. `msg1 "Bonjour Patrick"` → `<<PERSON:1>>`, then `msg2 "Alice est la"` → Alice also gets `<<PERSON:1>>` (collision).
2. With entity "Ali" in memory, `anonymize_with_ent("Alibaba ...")` → `<<PERSON:1>>baba`.
3. Blocking `pydantic` import makes `import piighost.anonymizer` fail although pydantic is only in the `config` extra.

---

### Task 1: Data model hardening (Span validation, masked Detection repr, Entity.canonical)

**Files:**
- Modify: `src/piighost/models.py`
- Modify: `src/piighost/linker/entity.py` (use `canonical_key` in `_group` seeds)
- Modify: `src/piighost/placeholder.py` (use `entity.canonical`)
- Modify: `src/piighost/resolver/entity.py` (FuzzyEntityConflictResolver uses `canonical`)
- Modify: `src/piighost/pipeline/thread.py` (`ConversationMemory._key` uses `canonical_key`)
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_models.py`:

```python
import pytest

from piighost.models import Detection, Entity, Span


def test_span_rejects_inverted_bounds():
    with pytest.raises(ValueError):
        Span(start_pos=5, end_pos=2)


def test_span_rejects_negative_start():
    with pytest.raises(ValueError):
        Span(start_pos=-1, end_pos=2)


def test_detection_repr_masks_pii():
    d = Detection(text="Patrick", label="PERSON", position=Span(0, 7), confidence=0.9)
    assert "Patrick" not in repr(d)
    assert "P***" in repr(d)
    # to_dict stays raw: it is the explicit serialization path.
    assert d.to_dict()["text"] == "Patrick"


def test_entity_canonical_properties():
    d = Detection(text="Patrick", label="PERSON", position=Span(0, 7), confidence=0.9)
    e = Entity(detections=(d,))
    assert e.canonical == "patrick"
    assert e.canonical_key == ("patrick", "PERSON")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models.py -v`
Expected: the four new tests FAIL (`ValueError` not raised, `Patrick` in repr, `AttributeError: canonical`).

- [ ] **Step 3: Implement in `src/piighost/models.py`**

Add to `Span`:

```python
    def __post_init__(self) -> None:
        if self.start_pos < 0 or self.end_pos < self.start_pos:
            raise ValueError(
                f"Invalid span bounds: start_pos={self.start_pos}, "
                f"end_pos={self.end_pos} (need 0 <= start_pos <= end_pos)"
            )
```

Add to `Detection` (and update its class docstring: the `text` attribute note about raw PII in `__repr__` becomes "masked in `__repr__`; use `to_dict()` for the raw value"):

```python
    def __repr__(self) -> str:
        masked = f"{self.text[:1]}***" if self.text else ""
        return (
            f"Detection(text={masked!r}, label={self.label!r}, "
            f"position={self.position!r}, confidence={self.confidence!r})"
        )
```

Add to `Entity`:

```python
    @property
    def canonical(self) -> str:
        """Lower-cased canonical surface text (first detection)."""
        return self.detections[0].text.lower()

    @property
    def canonical_key(self) -> tuple[str, str]:
        """Identity key ``(canonical, label)`` used for dedup and cross-message linking."""
        return (self.canonical, self.label)
```

- [ ] **Step 4: Replace the implicit convention at the three call sites**

In `src/piighost/linker/entity.py`, `ExactEntityLinker._group`, replace:

```python
                key = (entity.detections[0].text.lower(), entity.label)
```
with:
```python
                key = entity.canonical_key
```

In `src/piighost/resolver/entity.py`, `FuzzyEntityConflictResolver.have_conflict`, replace:

```python
        text_a = entity_a.detections[0].text.lower()
        text_b = entity_b.detections[0].text.lower()
```
with:
```python
        text_a = entity_a.canonical
        text_b = entity_b.canonical
```

In `src/piighost/placeholder.py`, in `LabelHashPlaceholderFactory.create` and `RedactHashPlaceholderFactory.create`, replace `canonical_text = entity.detections[0].text.lower()` with `canonical_text = entity.canonical`.

In `src/piighost/pipeline/thread.py`, `ConversationMemory._key`, replace the body with `return entity.canonical_key`.

Also update the `ConversationMemory` docstring example (it shows a full `Detection(text='Patrick', ...)` repr which is now masked):

```python
        >>> memory.record("abc123", [e])
        >>> memory.all_entities[0].canonical
        'patrick'
```

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest`
Expected: PASS (if a test asserted the old repr, update it to use `to_dict()`).

- [ ] **Step 6: Commit**

```bash
git add src/piighost/models.py src/piighost/linker/entity.py src/piighost/resolver/entity.py src/piighost/placeholder.py src/piighost/pipeline/thread.py tests/test_models.py
git commit -m "feat(models): validate Span bounds, mask Detection repr, add Entity.canonical"
```

---

### Task 2: Word-boundary replacement in `_replace_longest_first`

**Files:**
- Modify: `src/piighost/utils.py`
- Modify: `src/piighost/pipeline/thread.py`
- Test: `tests/pipeline/test_with_ent_boundaries.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/pipeline/test_with_ent_boundaries.py`:

```python
"""Word-boundary behaviour of anonymize_with_ent / deanonymize_with_ent."""

from piighost.anonymizer import Anonymizer
from piighost.detector.base import ExactMatchDetector
from piighost.pipeline.thread import ThreadAnonymizationPipeline


def _pipeline(*names: str) -> ThreadAnonymizationPipeline:
    detector = ExactMatchDetector([(n, "PERSON") for n in names])
    return ThreadAnonymizationPipeline(detector=detector, anonymizer=Anonymizer())


async def test_anonymize_with_ent_does_not_replace_inside_words():
    pipe = _pipeline("Ali")
    await pipe.anonymize("Ali est venu", thread_id="t")
    out = pipe.anonymize_with_ent("Alibaba et Ali", thread_id="t")
    assert out == "Alibaba et <<PERSON:1>>"


async def test_deanonymize_with_ent_replaces_token_glued_to_word():
    pipe = _pipeline("Patrick")
    await pipe.anonymize("Bonjour Patrick", thread_id="t")
    # LLM output may glue a token to a word; token replacement must not
    # require word boundaries (the << >> delimiters already isolate it).
    out = await pipe.deanonymize_with_ent("Bonjour<<PERSON:1>>!", thread_id="t")
    assert out == "BonjourPatrick!"
```

- [ ] **Step 2: Run tests to verify the first one fails**

Run: `uv run pytest tests/pipeline/test_with_ent_boundaries.py -v`
Expected: first test FAILS with `'<<PERSON:1>>baba et <<PERSON:1>>'`; second PASSES (current behaviour, must not regress).

- [ ] **Step 3: Extract the boundary helper in `src/piighost/utils.py`**

```python
def boundary_wrap(fragment: str) -> str:
    """Escape *fragment* and wrap it in word-boundary assertions.

    Uses ``\\b`` for alphanumeric/underscore edges and lookarounds
    ``(?<!\\w)`` / ``(?!\\w)`` for fragments starting or ending with
    special characters.
    """
    prefix = r"\b" if fragment[0:1].isalnum() or fragment[0:1] == "_" else r"(?<!\w)"
    suffix = r"\b" if fragment[-1:].isalnum() or fragment[-1:] == "_" else r"(?!\w)"
    return f"{prefix}{re.escape(fragment)}{suffix}"
```

And make `_word_boundary_pattern` use it:

```python
@lru_cache(maxsize=1024)
def _word_boundary_pattern(fragment: str, flags: int) -> re.Pattern[str]:
    """Compile (and cache) the word-boundary pattern for *fragment*."""
    return re.compile(boundary_wrap(fragment), flags)
```

- [ ] **Step 4: Add the `word_boundary` mode to `_replace_longest_first` in `src/piighost/pipeline/thread.py`**

```python
def _replace_longest_first(
    text: str,
    pairs: list[tuple[str, str]],
    *,
    word_boundary: bool = False,
) -> str:
    """Replace every *source* with its *target* in one regex pass.

    Sources are emitted longest-first in the alternation so that a match
    on a longer source wins over any shorter prefix.  Duplicate sources
    are collapsed: the first mapping wins.  Returns *text* unchanged
    when ``pairs`` is empty.

    When ``word_boundary`` is true, each source only matches at word
    boundaries.  Use it when sources are raw PII surface forms (so
    "Ali" does not match inside "Alibaba").  Leave it false when
    sources are placeholder tokens: their ``<<...>>`` delimiters
    already isolate them, and an LLM may glue a token to a word.
    """
    mapping: dict[str, str] = {}
    for source, target in pairs:
        if source and source not in mapping:
            mapping[source] = target

    if not mapping:
        return text

    sources = sorted(mapping, key=len, reverse=True)
    if word_boundary:
        alternation = "|".join(boundary_wrap(s) for s in sources)
    else:
        alternation = "|".join(re.escape(s) for s in sources)
    pattern = re.compile(alternation)
    return pattern.sub(lambda m: mapping[m.group(0)], text)
```

Add `from piighost.utils import boundary_wrap, hash_sha256` to the imports. In `anonymize_with_ent`, call `_replace_longest_first(text, pairs, word_boundary=True)`. `deanonymize_with_ent` keeps `word_boundary=False` (default).

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/pipeline/ tests/test_utils.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/piighost/utils.py src/piighost/pipeline/thread.py tests/pipeline/test_with_ent_boundaries.py
git commit -m "fix(pipeline): word-boundary matching in anonymize_with_ent replacement"
```

---

### Task 3: Decouple config from core (drop bottom imports, no-extras import test)

**Files:**
- Modify: `src/piighost/anonymizer.py`, `src/piighost/placeholder.py`, `src/piighost/linker/entity.py`, `src/piighost/resolver/span.py`, `src/piighost/resolver/entity.py`, `src/piighost/detector/base.py`, `src/piighost/detector/chunked.py`, `src/piighost/detector/gliner2.py`, `src/piighost/detector/spacy.py`, `src/piighost/detector/transformers.py`, `src/piighost/detector/llm.py`, `src/piighost/ph_factory/faker.py`, `src/piighost/ph_factory/faker_hash.py`
- Modify: `tests/config/test_from_config_detectors.py` (and any other test asserting `.Config`)
- Test: `tests/test_core_no_extras.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_core_no_extras.py`:

```python
"""The core package must import without any optional extra installed.

Runs in a subprocess so the parent test session (which has pydantic
installed and imported) cannot mask a hard dependency. A MetaPathFinder
raises ImportError for the blocked package, simulating its absence.
"""

import subprocess
import sys
import textwrap

CORE_MODULES = [
    "piighost",
    "piighost.anonymizer",
    "piighost.placeholder",
    "piighost.placeholder_tags",
    "piighost.detector.base",
    "piighost.linker.entity",
    "piighost.resolver.span",
    "piighost.resolver.entity",
    "piighost.guard",
    "piighost.models",
    "piighost.validators",
]


def _import_with_blocked(package: str) -> subprocess.CompletedProcess:
    code = textwrap.dedent(f"""
        import importlib.abc
        import sys

        class Blocker(importlib.abc.MetaPathFinder):
            def find_spec(self, name, path=None, target=None):
                if name == "{package}" or name.startswith("{package}."):
                    raise ImportError(name + " blocked (simulating missing extra)")

        sys.meta_path.insert(0, Blocker())
        import importlib
        for module in {CORE_MODULES!r}:
            importlib.import_module(module)
        print("ok")
    """)
    return subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )


def test_core_importable_without_pydantic():
    result = _import_with_blocked("pydantic")
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_core_no_extras.py -v`
Expected: FAIL with `pydantic blocked (simulating missing extra)` in stderr.

- [ ] **Step 3: Remove the coupling from every core module**

In each file listed above, delete:
1. The `Config: ClassVar[type["..."]]` class attribute declarations (and the now-unused `ClassVar` import if nothing else uses it).
2. The bottom-of-module `from piighost.config.models...` import block and the `X.Config = XConfig` assignments.

Keep the `from_config` classmethods and their `TYPE_CHECKING`-guarded config imports untouched (they never import pydantic at runtime; the validated config object is passed in by `config/builders.py`).

`config/builders.py` already dispatches `{ConfigClass: ComponentClass}` and never reads `.Config`, so no change is needed there.

- [ ] **Step 4: Update tests that asserted the attachment**

In `tests/config/test_from_config_detectors.py`, replace every `assert SomeDetector.Config is SomeDetectorConfig` with a dispatch assertion through the builder, e.g.:

```python
from piighost.config.builders import build_detector
from piighost.config.models.detector import RegexDetectorConfig
from piighost.detector.base import RegexDetector


def test_build_detector_dispatches_regex():
    cfg = RegexDetectorConfig(type="regex", patterns={"EMAIL": r"\S+@\S+"})
    detector = build_detector(cfg)
    assert isinstance(detector, RegexDetector)
```

Search for other `.Config` assertions first: `grep -rn "\.Config is\|\.Config ==" tests/` and convert them all the same way.

- [ ] **Step 5: Run the suite**

Run: `uv run pytest tests/test_core_no_extras.py tests/config/ -v && uv run pytest`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A src tests
git commit -m "fix(packaging): core no longer imports pydantic; config dispatch lives in builders only"
```

---

### Task 4: Real union-find resolver and parallel CompositeDetector

**Files:**
- Modify: `src/piighost/resolver/entity.py`
- Modify: `src/piighost/detector/base.py`
- Test: `tests/resolver/test_union_find.py` (create), existing `tests/detector/` suite

- [ ] **Step 1: Write the failing tests**

Create `tests/resolver/test_union_find.py`:

```python
"""Union-find semantics and complexity guard for MergeEntityConflictResolver."""

from piighost.models import Detection, Entity, Span
from piighost.resolver.entity import MergeEntityConflictResolver


def _det(text: str, start: int) -> Detection:
    return Detection(
        text=text, label="PERSON",
        position=Span(start, start + len(text)), confidence=0.9,
    )


def test_transitive_merge_through_shared_detections():
    a, b, c = _det("Patrick", 0), _det("Patrick", 20), _det("patric", 40)
    e1 = Entity(detections=(a, b))
    e2 = Entity(detections=(b, c))
    e3 = Entity(detections=(c,))
    result = MergeEntityConflictResolver().resolve([e1, e2, e3])
    assert len(result) == 1
    assert set(result[0].detections) == {a, b, c}


def test_disjoint_entities_preserved_and_position_sorted():
    e_late = Entity(detections=(_det("Bob", 50),))
    e_early = Entity(detections=(_det("Alice", 0),))
    result = MergeEntityConflictResolver().resolve([e_late, e_early])
    assert [e.detections[0].text for e in result] == ["Alice", "Bob"]


def test_resolve_scales_to_large_inputs():
    # The old fixpoint loop was cubic; 2000 disjoint entities must resolve fast.
    entities = [Entity(detections=(_det(f"p{i}", i * 10),)) for i in range(2000)]
    result = MergeEntityConflictResolver().resolve(entities)
    assert len(result) == 2000
```

- [ ] **Step 2: Run to check current behaviour**

Run: `uv run pytest tests/resolver/test_union_find.py -v --timeout=60`
Expected: the two semantic tests PASS (behaviour preserved), the scale test is slow or fails on time. If `pytest-timeout` is not installed, run without the flag and observe the duration.

- [ ] **Step 3: Replace `MergeEntityConflictResolver.resolve`**

```python
    def resolve(self, entities: list[Entity]) -> list[Entity]:
        """Merge all entities that share common detections, transitively.

        Uses union-find with path compression over entity indices:
        every conflicting pair is unioned, then each root's detections
        are concatenated (deduplicated, input order preserved).

        Args:
            entities: The full list of entities.

        Returns:
            A merged list of entities with no shared detections,
            sorted by earliest ``start_pos``.
        """
        if not entities:
            return []

        parent = list(range(len(entities)))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for i in range(len(entities)):
            for j in range(i + 1, len(entities)):
                if find(i) != find(j) and self.have_conflict(entities[i], entities[j]):
                    parent[find(j)] = find(i)

        merged: dict[int, list[Detection]] = {}
        seen: dict[int, set[Detection]] = {}
        for i, entity in enumerate(entities):
            root = find(i)
            bucket = merged.setdefault(root, [])
            known = seen.setdefault(root, set())
            for d in entity.detections:
                if d not in known:
                    known.add(d)
                    bucket.append(d)

        result = [Entity(detections=tuple(dets)) for dets in merged.values()]
        result.sort(key=lambda e: min(d.position.start_pos for d in e.detections))
        return result
```

Also update the class docstring (it already says "Union-Find"; now it is true) and delete the old fixpoint loop entirely.

- [ ] **Step 4: Parallelize `CompositeDetector.detect` in `src/piighost/detector/base.py`**

Add `import asyncio` at the top, then:

```python
    async def detect(self, text: str) -> list[Detection]:
        """Collect detections from every child detector, run concurrently.

        Args:
            text: The input text to search for entities.

        Returns:
            Concatenated list of detections, in detector order.
        """
        if not self.detectors:
            return []
        results = await asyncio.gather(*(d.detect(text) for d in self.detectors))
        return [detection for sublist in results for detection in sublist]
```

- [ ] **Step 5: Run the suite**

Run: `uv run pytest tests/resolver/ tests/detector/ -v && uv run pytest`
Expected: PASS, scale test well under a second.

- [ ] **Step 6: Commit**

```bash
git add src/piighost/resolver/entity.py src/piighost/detector/base.py tests/resolver/test_union_find.py
git commit -m "perf(resolver): true union-find merge; run composite detectors concurrently"
```

---

### Task 5: Token-aware guard rail

**Files:**
- Modify: `src/piighost/guard.py`
- Modify: `src/piighost/guard_llm.py`
- Test: `tests/test_guard.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_guard.py`:

```python
from piighost.detector.base import ExactMatchDetector
from piighost.guard import DetectorGuardRail, filter_token_overlaps
from piighost.models import Detection, Span


async def test_detector_guard_ignores_known_tokens():
    # A NER-ish detector that would flag the fake name used as a token.
    detector = ExactMatchDetector([("Jean Dupont", "PERSON")])
    guard = DetectorGuardRail(detector=detector)
    # The faker token IS the placeholder: must not raise.
    await guard.check("Bonjour Jean Dupont", tokens=["Jean Dupont"])


async def test_detector_guard_still_flags_real_residual_pii():
    detector = ExactMatchDetector([("Jean Dupont", "PERSON"), ("Alice", "PERSON")])
    guard = DetectorGuardRail(detector=detector)
    import pytest
    from piighost.exceptions import PIIRemainingError
    with pytest.raises(PIIRemainingError):
        await guard.check("Jean Dupont et Alice", tokens=["Jean Dupont"])


def test_filter_token_overlaps_drops_overlapping_detections():
    text = "Hello <<PERSON:1>> world"
    inside = Detection(text="PERSON", label="PERSON", position=Span(8, 14), confidence=1.0)
    outside = Detection(text="world", label="PERSON", position=Span(19, 24), confidence=1.0)
    kept = filter_token_overlaps([inside, outside], text, ["<<PERSON:1>>"])
    assert kept == [outside]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_guard.py -v`
Expected: FAIL (`check() got an unexpected keyword argument 'tokens'`, `ImportError: filter_token_overlaps`).

- [ ] **Step 3: Implement in `src/piighost/guard.py`**

Update the protocol and both implementations (new signature everywhere: `async def check(self, anonymized_text: str, tokens: Sequence[str] = ()) -> None`), add `from collections.abc import Sequence` and the helper:

```python
def filter_token_overlaps(
    detections: list[Detection],
    text: str,
    tokens: Sequence[str],
) -> list[Detection]:
    """Drop detections that overlap an occurrence of a known placeholder token.

    Guards re-run detectors on the anonymized output; with realistic
    factories (Faker) the placeholders themselves are detectable. The
    pipeline therefore forwards the tokens it just emitted, and any
    detection overlapping one of their occurrences is discarded.
    """
    spans: list[tuple[int, int]] = []
    for token in tokens:
        if not token:
            continue
        start = text.find(token)
        while start != -1:
            spans.append((start, start + len(token)))
            start = text.find(token, start + 1)
    if not spans:
        return list(detections)
    return [
        d
        for d in detections
        if not any(
            d.position.start_pos < end and start < d.position.end_pos
            for start, end in spans
        )
    ]
```

`DetectorGuardRail.check` becomes:

```python
    async def check(self, anonymized_text: str, tokens: Sequence[str] = ()) -> None:
        residual = await self._detector.detect(anonymized_text)
        residual = filter_token_overlaps(residual, anonymized_text, tokens)
        if residual:
            raise PIIRemainingError(
                f"{len(residual)} residual detection(s) found in anonymized text",
                detections=list(residual),
            )
```

`DisabledGuardRail.check` gains the `tokens: Sequence[str] = ()` parameter (body unchanged). Import `Detection` from `piighost.models`. Add `filter_token_overlaps` to `__all__`.

- [ ] **Step 4: Mirror in `src/piighost/guard_llm.py`**

`LLMGuardRail.check`:

```python
    async def check(self, anonymized_text: str, tokens: Sequence[str] = ()) -> None:
        from piighost.guard import filter_token_overlaps

        residual = await self._detector.detect(anonymized_text)
        residual = filter_token_overlaps(residual, anonymized_text, tokens)
        if residual:
            raise PIIRemainingError(
                f"{len(residual)} residual detection(s) reported by LLM",
                detections=list(residual),
            )
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_guard.py tests/test_guard_llm.py -v`
Expected: PASS (existing tests unaffected: `tokens` has a default).

- [ ] **Step 6: Commit**

```bash
git add src/piighost/guard.py src/piighost/guard_llm.py tests/test_guard.py
git commit -m "feat(guard): token-aware check() ignores the placeholders the pipeline emitted"
```

---

### Task 6: Single `_anonymize_with_span` template method + async observation pacing

**Files:**
- Modify: `src/piighost/observation/base.py` (add `needs_timestamp_spacing`)
- Modify: `src/piighost/observation/langfuse.py`, `src/piighost/observation/opik.py`
- Modify: `src/piighost/pipeline/base.py`
- Modify: `src/piighost/pipeline/thread.py`
- Test: `tests/pipeline/test_obs_pacing.py` (create), existing pipeline suite

- [ ] **Step 1: Write the failing test**

Create `tests/pipeline/test_obs_pacing.py`:

```python
"""The pipeline must not block the event loop with time.sleep."""

import time

from piighost.anonymizer import Anonymizer
from piighost.detector.base import ExactMatchDetector
from piighost.pipeline.base import AnonymizationPipeline
from piighost.pipeline.thread import ThreadAnonymizationPipeline


async def test_no_pacing_overhead_without_observation_backend():
    pipe = AnonymizationPipeline(
        detector=ExactMatchDetector([("Patrick", "PERSON")]),
        anonymizer=Anonymizer(),
    )
    start = time.perf_counter()
    for i in range(50):
        await pipe.anonymize(f"Bonjour Patrick numero {i}")
    elapsed = time.perf_counter() - start
    # 50 runs x 4 stages x 1ms sleep would be >= 0.2s; without pacing
    # this loop finishes far quicker.
    assert elapsed < 0.15


def test_source_has_no_blocking_sleep():
    import inspect
    import piighost.pipeline.base as base
    import piighost.pipeline.thread as thread
    assert "time.sleep" not in inspect.getsource(base)
    assert "time.sleep" not in inspect.getsource(thread)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/pipeline/test_obs_pacing.py -v`
Expected: both FAIL (`time.sleep` present, elapsed > 0.2 s).

- [ ] **Step 3: Add the pacing flag to observation services**

In `src/piighost/observation/base.py`, on `AbstractObservationService`:

```python
    needs_timestamp_spacing: bool = False
    """Whether the pipeline should space consecutive stage observations
    by ~1 ms.  Langfuse (and Opik) store observation timestamps with
    millisecond precision and tie-break by random ID, so two stages
    starting in the same millisecond render in arbitrary order in the
    trace timeline.  The Python SDKs expose no public ``start_time``
    parameter (only OTel internals do), so pacing the producer is the
    only stable workaround.  Backends that do not need it (the NoOp
    default) keep ``False`` and pay zero latency."""
```

In `LangfuseObservationService` and `OpikObservationService`, add the class attribute `needs_timestamp_spacing = True`.

- [ ] **Step 4: Refactor `src/piighost/pipeline/base.py`**

Add `import asyncio` to the imports, remove `import time`. Replace `_anonymize_with_span` with the template method plus hooks (this is the single shared implementation; the thread subclass will only override the hooks):

```python
    async def _obs_pause(self) -> None:
        """Space consecutive stage observations by ~1 ms when the backend asks.

        Non-blocking (``asyncio.sleep``), and skipped entirely for
        backends that do not set ``needs_timestamp_spacing`` (NoOp).
        See ``AbstractObservationService.needs_timestamp_spacing``.
        """
        if getattr(self._observation, "needs_timestamp_spacing", False):
            await asyncio.sleep(0.001)

    def _link_stage(self, text: str, detections: list[Detection]) -> list[Entity]:
        """Link detections into entities and resolve conflicts.

        Subclasses extend this to add cross-message linking.
        """
        entities = self._entity_linker.link(text, detections)
        return self._entity_resolver.resolve(entities)

    async def _record_entities(self, text: str, entities: list[Entity]) -> None:
        """Hook called after linking; the base pipeline keeps no memory."""
        return None

    def _render_stage(self, text: str, entities: list[Entity]) -> tuple[str, list[str]]:
        """Render the anonymized text; returns ``(anonymized, tokens)``.

        Tokens are forwarded to the guard rail so it can ignore the
        placeholders the pipeline itself just emitted.
        """
        token_map = self.ph_factory.create(entities)
        return self._anonymizer.anonymize(text, entities), list(token_map.values())

    async def _anonymize_with_span(
        self,
        text: str,
        root_span: AbstractSpan,
    ) -> Tuple[str, list[Entity]]:
        """Execute all pipeline stages, emitting child observations on *root_span*."""
        # Detect
        with root_span.start_as_current_observation(
            name="piighost.detect",
            as_type="tool",
        ) as span:
            detections = await self._cached_detect(text)
            obs_text_pre_link = self._obs_text(
                text, [Entity(detections=(d,)) for d in detections]
            )
            root_span.update(input={"text": obs_text_pre_link})
            span.update(
                input={"text": obs_text_pre_link},
                output={"detections": self._obs_detections_to_dicts(detections)},
            )
            detections = self._span_resolver.resolve(detections)
            await self._obs_pause()

        # Link
        with root_span.start_as_current_observation(
            name="piighost.link",
            as_type="span",
        ) as span:
            entities = self._link_stage(text, detections)
            ent_tokens = (
                self._obs_ph_factory.create(entities)
                if self._obs_ph_factory is not None
                else {}
            )
            span.update(
                input={"detections": self._obs_detections_to_dicts(detections)},
                output={
                    "entities": [
                        _entity_to_dict(e, token=ent_tokens[e] if ent_tokens else None)
                        for e in entities
                    ]
                },
            )
            await self._obs_pause()

        await self._record_entities(text, entities)

        # Placeholder
        with root_span.start_as_current_observation(
            name="piighost.placeholder",
            as_type="tool",
        ) as span:
            anonymized, tokens = self._render_stage(text, entities)
            obs_text = self._obs_text(text, entities)
            span.update(
                input={"text": obs_text, "entity_count": len(entities)},
                output={"text": anonymized},
            )
            await self._obs_pause()

        # Guard
        with root_span.start_as_current_observation(
            name="piighost.guard",
            as_type="guardrail",
        ) as span:
            span.update(input={"text": anonymized})
            try:
                await self._guard_rail.check(anonymized, tokens=tokens)
            except PIIRemainingError:
                span.update(output={"passed": False})
                raise
            span.update(output={"passed": True})
            await self._obs_pause()

        root_span.update(
            output={"text": anonymized, "entity_count": len(entities)},
        )

        await self._store_mapping(text, anonymized, entities)
        await self._store_anon_result(text, anonymized, entities)
        return anonymized, entities
```

Both `anonymize` call sites in base drop the `metadata=` argument when calling `_anonymize_with_span` (the parameter was unused inside; metadata still flows into the root span creation in `anonymize`).

- [ ] **Step 5: Refactor `src/piighost/pipeline/thread.py`**

Delete the entire `_anonymize_with_span` override. Replace it with the three hook overrides (each reads the thread id from the ContextVar, which `anonymize` now sets around the whole call):

```python
    def _link_stage(self, text: str, detections: list[Detection]) -> list[Entity]:
        """Single-text linking plus cross-message linking against memory."""
        thread_id = _current_thread_id.get()
        entities = super()._link_stage(text, detections)
        return self._entity_linker.link_entities(
            entities,
            self.get_memory(thread_id).all_entities,
        )

    async def _record_entities(self, text: str, entities: list[Entity]) -> None:
        thread_id = _current_thread_id.get()
        self.get_memory(thread_id).record(hash_sha256(text), entities)

    def _render_stage(self, text: str, entities: list[Entity]) -> tuple[str, list[str]]:
        """Render via the conversation-wide replacement pass.

        Conversation entities carry detection positions from other
        messages, so span-based replacement does not apply; the
        longest-first word-boundary pass over all known surface forms
        is used instead.
        """
        thread_id = _current_thread_id.get()
        resolved = self.get_resolved_entities(thread_id)
        token_map = self.ph_factory.create(resolved)
        return (
            self.anonymize_with_ent(text, thread_id=thread_id),
            list(token_map.values()),
        )
```

And `anonymize` becomes the single ContextVar owner:

```python
    async def anonymize(
        self,
        text: str,
        thread_id: str = "default",
        *,
        metadata: Mapping[str, Any] | None = None,
        root_span: AbstractSpan | None = None,
    ) -> tuple[str, list[Entity]]:
        """Run detection, record entities in memory, then anonymize.

        Uses ``all_entities`` from memory for token creation so that
        counters stay consistent across messages.

        Args:
            text: The original text to anonymize.
            thread_id: Thread identifier for memory and cache isolation.
            metadata: Optional metadata forwarded to the observation trace.
            root_span: Caller-supplied root span. When provided the pipeline
                nests its stage observations under it and does not create a
                new root span from the configured observation service.

        Returns:
            A tuple of (anonymized text, entities used for anonymization).
        """
        token = _current_thread_id.set(thread_id)
        try:
            cached = await self._cache_get_anon_result(text)
            if cached is not None:
                entities = self._deserialize_entities(cached["entities"])
                await self._record_entities(text, entities)
                return cached["anonymized"], entities

            if root_span is not None:
                return await self._anonymize_with_span(text, root_span)

            with self._observation.start_as_current_span(
                name="piighost.anonymize_pipeline",
                session_id=thread_id if thread_id != "default" else None,
                metadata=dict(metadata) if metadata else None,
            ) as auto_root:
                return await self._anonymize_with_span(text, auto_root)
        finally:
            _current_thread_id.reset(token)
```

Remove `import time` from thread.py. (Note: `_record_entities` is extended again in Task 7 with cache persistence; here it only wraps `memory.record`.)

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest`
Expected: PASS, including `tests/pipeline/test_obs_pacing.py`.

- [ ] **Step 7: Commit**

```bash
git add src/piighost/observation src/piighost/pipeline tests/pipeline/test_obs_pacing.py
git commit -m "refactor(pipeline): single stage template with hooks; async opt-in observation pacing"
```

---

### Task 7: Stable first-seen token ordering + cache-backed, injectable memory

This is the fix for the critical collision bug. Two mechanisms: (a) `get_resolved_entities` returns entities in **first-seen order** (memory insertion order), never re-sorted by span position; (b) memory is hydrated from / persisted to the cache backend so every worker sees the same first-seen order.

**Files:**
- Modify: `src/piighost/pipeline/thread.py`
- Test: `tests/pipeline/test_token_stability.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/pipeline/test_token_stability.py`:

```python
"""Placeholder identity must be stable across messages and workers."""

from aiocache import SimpleMemoryCache

from piighost.anonymizer import Anonymizer
from piighost.detector.base import ExactMatchDetector
from piighost.pipeline.thread import ThreadAnonymizationPipeline


def _detector() -> ExactMatchDetector:
    return ExactMatchDetector([("Patrick", "PERSON"), ("Alice", "PERSON")])


def _pipeline(cache=None) -> ThreadAnonymizationPipeline:
    return ThreadAnonymizationPipeline(
        detector=_detector(), anonymizer=Anonymizer(), cache=cache
    )


async def test_counter_not_stolen_by_earlier_position_in_later_message():
    pipe = _pipeline()
    a1, _ = await pipe.anonymize("Bonjour Patrick", thread_id="t")
    # Alice appears at position 0, earlier than Patrick's old span(8, 15):
    # she must still get the NEXT counter, not steal <<PERSON:1>>.
    a2, _ = await pipe.anonymize("Alice est la", thread_id="t")
    assert a1 == "Bonjour <<PERSON:1>>"
    assert a2 == "<<PERSON:2>> est la"

    restored = await pipe.deanonymize_with_ent(
        "<<PERSON:1>> et <<PERSON:2>>", thread_id="t"
    )
    assert restored == "Patrick et Alice"


async def test_token_ordering_shared_across_workers_via_cache():
    cache = SimpleMemoryCache()
    worker_a = _pipeline(cache)
    worker_b = _pipeline(cache)

    a1, _ = await worker_a.anonymize("Bonjour Patrick", thread_id="t")
    # worker_b never saw message 1; it must hydrate memory from the cache.
    a2, _ = await worker_b.anonymize("Alice est la", thread_id="t")
    assert a1 == "Bonjour <<PERSON:1>>"
    assert a2 == "<<PERSON:2>> est la"

    # And worker_a must learn about Alice for deanonymization.
    restored = await worker_a.deanonymize_with_ent("<<PERSON:2>>", thread_id="t")
    assert restored == "Alice"


async def test_threads_stay_isolated():
    pipe = _pipeline()
    a1, _ = await pipe.anonymize("Bonjour Patrick", thread_id="t1")
    a2, _ = await pipe.anonymize("Alice est la", thread_id="t2")
    # Separate threads each start their own numbering.
    assert a1 == "Bonjour <<PERSON:1>>"
    assert a2 == "<<PERSON:1>> est la"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pipeline/test_token_stability.py -v`
Expected: first two tests FAIL (`<<PERSON:1>> est la` from the position re-sort; worker_b blind to worker_a's entities). Isolation test passes.

- [ ] **Step 3: Add serialization to `ConversationMemory`**

In `src/piighost/pipeline/thread.py`:

```python
    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly snapshot preserving insertion (first-seen) order."""
        return {
            "entities_by_hash": {
                text_hash: [e.to_dict() for e in bucket]
                for text_hash, bucket in self.entities_by_hash.items()
            }
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConversationMemory":
        """Rebuild a memory by replaying the snapshot through ``record``."""
        memory = cls()
        memory.merge_snapshot(data)
        return memory

    def merge_snapshot(self, data: dict[str, Any]) -> None:
        """Replay *data* into this memory; idempotent (record dedups)."""
        for text_hash, bucket in data.get("entities_by_hash", {}).items():
            self.record(text_hash, [Entity.from_dict(e) for e in bucket])
```

Extend the `AnyConversationMemory` protocol accordingly:

```python
class AnyConversationMemory(Protocol):
    """Protocol for conversation memory implementations."""

    entities_by_hash: dict[str, list[Entity]]

    @property
    def all_entities(self) -> list[Entity]: ...

    def record(self, text_hash: str, entities: list[Entity]) -> None: ...

    def to_dict(self) -> dict[str, Any]: ...

    def merge_snapshot(self, data: dict[str, Any]) -> None: ...
```

- [ ] **Step 4: Make memory injectable and cache-backed in `ThreadAnonymizationPipeline`**

Constructor gains a factory parameter (add to the docstring Args):

```python
        memory_factory: Callable[[], AnyConversationMemory] | None = None,
```
```python
        self._memory_factory: Callable[[], AnyConversationMemory] = (
            memory_factory or ConversationMemory
        )
        self._memories: OrderedDict[str, AnyConversationMemory] = OrderedDict()
```

`get_memory` instantiates via `self._memory_factory()` instead of `ConversationMemory()`. Add `from collections.abc import Callable` to imports if absent (note: `typing.Protocol` import already present).

Add the memory cache key helper and hydration:

```python
    @staticmethod
    def _memory_key(thread_id: str) -> str:
        """Cache key holding the serialized conversation memory snapshot."""
        return f"{thread_id}:piighost:memory"

    async def _hydrate_memory(self, thread_id: str) -> None:
        """Merge the cached memory snapshot for *thread_id* into RAM.

        Called at the top of every async entry point so a worker that
        did not process earlier messages still sees the entities (and
        therefore the first-seen token ordering) recorded by another
        worker through the shared cache backend.  Replay is idempotent;
        concurrent writers are last-write-wins, which is acceptable for
        alternating turns of a single conversation.
        """
        snapshot = await self._cache.get(self._memory_key(thread_id))
        if snapshot is not None:
            self.get_memory(thread_id).merge_snapshot(snapshot)

    async def _persist_memory(self, thread_id: str) -> None:
        """Write the thread's memory snapshot through to the cache backend."""
        memory = self.get_memory(thread_id)
        await self._cache.set(
            self._memory_key(thread_id),
            memory.to_dict(),
            ttl=self._cache_ttl,
        )
```

Override `_record_entities` (replacing the Task 6 version) to persist write-through:

```python
    async def _record_entities(self, text: str, entities: list[Entity]) -> None:
        thread_id = _current_thread_id.get()
        self.get_memory(thread_id).record(hash_sha256(text), entities)
        await self._persist_memory(thread_id)
```

Call `await self._hydrate_memory(thread_id)` as the first statement inside the `try:` of `anonymize` (before the cache short-circuit), and at the top of `deanonymize_with_ent` and `override_detections`.

- [ ] **Step 5: Stable first-seen ordering in `get_resolved_entities`**

```python
    def get_resolved_entities(self, thread_id: str = "default") -> list[Entity]:
        """All entities from the thread's memory, merged then first-seen ordered.

        The entity resolver may merge entities and sorts its output by
        span position; positions come from different messages, so that
        order is meaningless here and, worse, unstable (a new entity
        early in its message would steal the counter of an older one).
        Re-rank by first-seen order from memory so counter-based
        factories assign stable tokens for the whole conversation.
        """
        all_entities = self.get_memory(thread_id).all_entities
        if not all_entities:
            return []
        rank = {e.canonical_key: i for i, e in enumerate(all_entities)}
        fallback = len(rank)
        resolved = self._entity_resolver.resolve(all_entities)
        resolved.sort(
            key=lambda e: min(
                rank.get((d.text.lower(), d.label), fallback) for d in e.detections
            )
        )
        return resolved
```

- [ ] **Step 6: Run the new tests, then the full suite**

Run: `uv run pytest tests/pipeline/test_token_stability.py -v && uv run pytest`
Expected: PASS. Some existing thread-pipeline tests may assert the old position-sorted numbering across messages; inspect each failure and update the expectation only when the old expectation encodes the buggy renumbering.

- [ ] **Step 7: Commit**

```bash
git add src/piighost/pipeline/thread.py tests/pipeline/test_token_stability.py
git commit -m "fix(pipeline): stable first-seen token ordering; cache-backed injectable memory"
```

---

### Task 8: `forget_thread`, default TTL 1h, per-thread key index, middleware log redaction

**Files:**
- Modify: `src/piighost/pipeline/base.py` (DEFAULT_CACHE_TTL)
- Modify: `src/piighost/pipeline/thread.py`
- Modify: `src/piighost/middleware.py`
- Test: `tests/pipeline/test_forget_thread.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/pipeline/test_forget_thread.py`:

```python
"""forget_thread must erase memory and every cache entry of the thread."""

from aiocache import SimpleMemoryCache

from piighost.anonymizer import Anonymizer
from piighost.detector.base import ExactMatchDetector
from piighost.exceptions import CacheMissError
from piighost.pipeline.base import DEFAULT_CACHE_TTL
from piighost.pipeline.thread import ThreadAnonymizationPipeline


def _pipeline(cache=None) -> ThreadAnonymizationPipeline:
    return ThreadAnonymizationPipeline(
        detector=ExactMatchDetector([("Patrick", "PERSON")]),
        anonymizer=Anonymizer(),
        cache=cache,
    )


def test_default_ttl_is_one_hour():
    assert DEFAULT_CACHE_TTL == 3600
    pipe = _pipeline()
    assert pipe._cache_ttl == 3600


async def test_forget_thread_erases_cache_and_memory():
    cache = SimpleMemoryCache()
    pipe = _pipeline(cache)
    anonymized, _ = await pipe.anonymize("Bonjour Patrick", thread_id="t")

    await pipe.forget_thread("t")

    # Memory gone: nothing left to replace.
    assert pipe.anonymize_with_ent("Patrick", thread_id="t") == "Patrick"
    # Mappings gone: deanonymize misses.
    import pytest
    with pytest.raises(CacheMissError):
        await pipe.deanonymize(anonymized, thread_id="t")
    # No stray thread-scoped keys survive in the backend.
    leftover = [k for k in cache._cache.keys() if str(k).startswith("t:")]
    assert leftover == []


async def test_forget_thread_does_not_touch_other_threads():
    pipe = _pipeline()
    await pipe.anonymize("Bonjour Patrick", thread_id="keep")
    await pipe.anonymize("Bonjour Patrick", thread_id="drop")
    await pipe.forget_thread("drop")
    assert pipe.anonymize_with_ent("Patrick", thread_id="keep") == "<<PERSON:1>>"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pipeline/test_forget_thread.py -v`
Expected: FAIL (`ImportError: DEFAULT_CACHE_TTL`, `AttributeError: forget_thread`).

- [ ] **Step 3: Default TTL in `src/piighost/pipeline/base.py`**

```python
DEFAULT_CACHE_TTL: int = 3600
"""Default time-to-live (seconds) for every cache entry the pipeline writes.

Cache entries hold raw PII (original texts and entity surface forms),
so unbounded retention is not an acceptable default.  Pass
``cache_ttl=None`` explicitly to keep entries until backend eviction.
"""
```

Both `AnonymizationPipeline.__init__` and `ThreadAnonymizationPipeline.__init__` change the parameter default from `cache_ttl: int | None = None` to `cache_ttl: int | None = DEFAULT_CACHE_TTL`, with the docstring updated ("Defaults to one hour; ``None`` keeps entries until the backend evicts them").

- [ ] **Step 4: Indexed writes and `forget_thread` in `src/piighost/pipeline/thread.py`**

```python
    @staticmethod
    def _key_index_key(thread_id: str) -> str:
        """Cache key listing every thread-scoped key the pipeline wrote."""
        return f"{thread_id}:piighost:keys"

    async def _cache_set_indexed(self, thread_id: str, key: str, value: Any) -> None:
        """Write *key* and register it in the thread's key index.

        The index is what makes ``forget_thread`` possible on backends
        without prefix deletion (aiocache has no portable scan). The
        index itself carries no TTL so that ``forget_thread`` still
        finds keys whose entries already expired; it is deleted by
        ``forget_thread`` and bounded by the number of distinct texts
        in the conversation.
        """
        await self._cache.set(key, value, ttl=self._cache_ttl)
        index_key = self._key_index_key(thread_id)
        index: list[str] = await self._cache.get(index_key) or []
        if key not in index:
            index.append(key)
            await self._cache.set(index_key, index, ttl=None)

    async def forget_thread(self, thread_id: str) -> None:
        """Erase every trace of *thread_id*: RAM memory and cache entries.

        Intended for end-of-conversation cleanup and right-to-be-forgotten
        requests (used by piighost-api). Idempotent.
        """
        index_key = self._key_index_key(thread_id)
        index: list[str] = await self._cache.get(index_key) or []
        for key in index:
            await self._cache.delete(key)
        await self._cache.delete(index_key)
        self._memories.pop(thread_id, None)
```

Route every thread-scoped write through `_cache_set_indexed`:
- `_store_mapping` and `_store_anon_result`: replace `await self._cache.set(key, {...}, ttl=self._cache_ttl)` with `await self._cache_set_indexed(thread_id, key, {...})`.
- `_cached_detect` (the set after a fresh detection): same change.
- `override_detections`: the `detect_key` write becomes `await self._cache_set_indexed(thread_id, detect_key, value)`.
- `_persist_memory` (from Task 7): replace its direct `self._cache.set` with `await self._cache_set_indexed(thread_id, self._memory_key(thread_id), memory.to_dict())`.

`clear_memory`'s docstring gains: "Only drops the in-RAM memory; use ``forget_thread`` to also purge the cache backend."

- [ ] **Step 5: Redact middleware debug logs in `src/piighost/middleware.py`**

Replace the `logger.debug` call in `abefore_model`:

```python
            logger.debug(
                "[PII] msg %d (%s): %d chars -> %d chars, %d entities (%s)",
                idx,
                type(message).__name__,
                len(content),
                len(result),
                len(ents),
                [e.label for e in ents],
            )
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/pipeline/test_forget_thread.py tests/ -v`
Expected: PASS. (`SimpleMemoryCache._cache` is the documented in-memory dict of aiocache; if the attribute differs in the pinned version, assert via `await cache.get(...) is None` on the keys captured before forgetting.)

- [ ] **Step 7: Commit**

```bash
git add src/piighost/pipeline tests/pipeline/test_forget_thread.py src/piighost/middleware.py
git commit -m "feat(pipeline): forget_thread purge API, 1h default cache TTL, redacted middleware logs"
```

---

### Task 9: Middleware: recursive tool-arg deanonymization + `require_thread_id`

**Files:**
- Modify: `src/piighost/middleware.py`
- Test: `tests/test_middleware.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_middleware.py` (reuse the file's existing fixtures/stubs for pipeline and requests; the essential assertions):

```python
async def test_wrap_tool_call_deanonymizes_nested_args(thread_pipeline_with_patrick):
    """Placeholders nested in dict / list args must be restored."""
    middleware = PIIAnonymizationMiddleware(pipeline=thread_pipeline_with_patrick)
    await thread_pipeline_with_patrick.anonymize("Bonjour Patrick", thread_id="default")

    captured = {}

    async def handler(request):
        captured.update(request.tool_call["args"])
        return ToolMessage(content="ok", tool_call_id="1")

    request = make_tool_call_request(
        args={
            "query": "<<PERSON:1>>",
            "filters": {"name": "<<PERSON:1>>", "depth": 2},
            "tags": ["<<PERSON:1>>", 42],
        }
    )
    await middleware.awrap_tool_call(request, handler)
    assert captured["query"] == "Patrick"
    assert captured["filters"] == {"name": "Patrick", "depth": 2}
    assert captured["tags"] == ["Patrick", 42]


async def test_require_thread_id_raises_outside_runnable_context(thread_pipeline_with_patrick):
    middleware = PIIAnonymizationMiddleware(
        pipeline=thread_pipeline_with_patrick, require_thread_id=True
    )
    import pytest
    with pytest.raises(ValueError, match="thread_id"):
        middleware._get_thread_id()
```

Adapt fixture names to the helpers that already exist in `tests/test_middleware.py` (there are existing tool-call tests to copy the request-building from).

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_middleware.py -v -k "nested or require"`
Expected: FAIL (nested values untouched; `_get_thread_id` is a module function, no strict mode).

- [ ] **Step 3: Implement in `src/piighost/middleware.py`**

Turn `_get_thread_id` into a method honouring strictness (keep a module-level `_missing_thread_id_warned` flag so the warning fires once per process):

```python
_missing_thread_id_warned: bool = False


class PIIAnonymizationMiddleware(AgentMiddleware):
    def __init__(
        self,
        pipeline: ThreadAnonymizationPipeline[PreservesIdentity],
        tool_strategy: ToolCallStrategy = ToolCallStrategy.FULL,
        require_thread_id: bool = False,
    ) -> None:
        super().__init__()
        self._pipeline = pipeline
        self.tool_strategy = tool_strategy
        self._require_thread_id = require_thread_id

    def _get_thread_id(self) -> str:
        """Extract the thread id from the LangGraph runtime config.

        Without a thread id every conversation shares the ``"default"``
        thread (cross-conversation placeholder leakage). With
        ``require_thread_id=True`` that fallback becomes an error.
        """
        global _missing_thread_id_warned
        try:
            thread_id = get_config().get("configurable", {}).get("thread_id")
        except RuntimeError:
            thread_id = None
        if thread_id is not None:
            return thread_id
        if self._require_thread_id:
            raise ValueError(
                "No thread_id in the LangGraph config and require_thread_id=True; "
                "set config={'configurable': {'thread_id': ...}} on the agent call."
            )
        if not _missing_thread_id_warned:
            _missing_thread_id_warned = True
            logger.warning(
                "No thread_id in the LangGraph config; falling back to the shared "
                "'default' thread. Distinct conversations will share placeholder "
                "state. Pass config={'configurable': {'thread_id': ...}} or use "
                "require_thread_id=True to fail fast."
            )
        return "default"
```

Update the three hook call sites from `_get_thread_id()` to `self._get_thread_id()`.

Add the recursive helper and use it in `awrap_tool_call`:

```python
    async def _deanonymize_value(self, value: Any, thread_id: str) -> Any:
        """Recursively deanonymize strings inside nested containers."""
        if isinstance(value, str):
            return await self._deanonymize(value, thread_id=thread_id)
        if isinstance(value, dict):
            return {
                key: await self._deanonymize_value(item, thread_id)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            items = [await self._deanonymize_value(item, thread_id) for item in value]
            return tuple(items) if isinstance(value, tuple) else items
        return value
```

In `awrap_tool_call`, replace the per-arg loop with:

```python
        call = request.tool_call
        call["args"] = await self._deanonymize_value(dict(call["args"]), thread_id)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_middleware.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/piighost/middleware.py tests/test_middleware.py
git commit -m "feat(middleware): recursive tool-arg deanonymization and require_thread_id strict mode"
```

---

### Task 10: Complete the TOML configs (and fix MaskPlaceholderFactory strategy merge)

**Files:**
- Modify: `src/piighost/config/models/span_resolver.py`, `.../entity_linker.py`, `.../placeholder.py`, `.../detector.py`
- Modify: `src/piighost/resolver/span.py`, `src/piighost/linker/entity.py`, `src/piighost/placeholder.py`, `src/piighost/detector/base.py` (the `from_config` bodies)
- Test: `tests/config/test_config_completeness.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/config/test_config_completeness.py`:

```python
"""Every operationally relevant constructor parameter must be reachable from TOML."""

import re

from piighost.config.models.detector import RegexDetectorConfig
from piighost.config.models.entity_linker import ExactEntityLinkerConfig
from piighost.config.models.placeholder import (
    LabelHashPlaceholderConfig,
    MaskPlaceholderConfig,
    RedactCounterPlaceholderConfig,
    RedactHashPlaceholderConfig,
    RedactPlaceholderConfig,
)
from piighost.config.models.span_resolver import ConfidenceSpanResolverConfig
from piighost.detector.base import RegexDetector
from piighost.linker.entity import ExactEntityLinker
from piighost.placeholder import (
    LabelHashPlaceholderFactory,
    MaskPlaceholderFactory,
    RedactCounterPlaceholderFactory,
    RedactHashPlaceholderFactory,
    RedactPlaceholderFactory,
)
from piighost.resolver.span import ConfidenceSpanConflictResolver
from piighost.validators import validate_luhn


def test_confidence_threshold_flows_from_config():
    cfg = ConfidenceSpanResolverConfig(confidence_threshold=0.6)
    resolver = ConfidenceSpanConflictResolver.from_config(cfg)
    assert resolver._confidence_threshold == 0.6


def test_linker_options_flow_from_config():
    cfg = ExactEntityLinkerConfig(min_text_length=3, case_sensitive=True)
    linker = ExactEntityLinker.from_config(cfg)
    assert linker._min_text_length == 3
    assert linker._flags == re.RegexFlag(0)


def test_redact_value_and_prefixes_flow_from_config():
    assert RedactPlaceholderFactory.from_config(
        RedactPlaceholderConfig(type="redact", value="HIDDEN")
    )._token == "<<HIDDEN>>"
    assert RedactCounterPlaceholderFactory.from_config(
        RedactCounterPlaceholderConfig(type="redact_counter", prefix="X")
    )._prefix == "X"
    factory = RedactHashPlaceholderFactory.from_config(
        RedactHashPlaceholderConfig(type="redact_hash", prefix="X", salt="s1")
    )
    assert factory._prefix == "X" and factory._salt == "s1"


def test_label_hash_salt_flows_from_config():
    factory = LabelHashPlaceholderFactory.from_config(
        LabelHashPlaceholderConfig(type="label_hash", salt="s1", hash_length=12)
    )
    assert factory._salt == "s1" and factory._hash_length == 12


def test_mask_visible_chars_flow_from_config():
    factory = MaskPlaceholderFactory.from_config(
        MaskPlaceholderConfig(type="mask", mask_char="#", visible_chars=2)
    )
    # The numeric default strategy must honour visible_chars.
    assert factory._strategies["phone"]("0612345678", "#") == "########78"


def test_regex_validators_flow_from_config():
    cfg = RegexDetectorConfig(
        type="regex",
        patterns={"CREDIT_CARD": r"\b\d{13,19}\b"},
        validators={"CREDIT_CARD": "luhn"},
    )
    detector = RegexDetector.from_config(cfg)
    assert detector.validators["CREDIT_CARD"] is validate_luhn


def test_mask_user_strategies_merge_on_top_of_defaults():
    factory = MaskPlaceholderFactory(strategies={"CUSTOM": lambda t, mc: "X"})
    # The custom label works AND the email default is still present.
    assert "email" in factory._strategies
    assert factory._strategies["custom"]("anything", "*") == "X"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/config/test_config_completeness.py -v`
Expected: FAIL (unknown config fields rejected by `extra="forbid"`, merge test fails).

- [ ] **Step 3: Extend the config models**

`src/piighost/config/models/span_resolver.py`:

```python
class ConfidenceSpanResolverConfig(_ComponentConfig):
    type: Literal["confidence"] = "confidence"
    confidence_threshold: float = Field(default=0.0, ge=0.0, le=1.0)
```
(add `Field` to the pydantic import)

`src/piighost/config/models/entity_linker.py`:

```python
class ExactEntityLinkerConfig(_ComponentConfig):
    type: Literal["exact"] = "exact"
    min_text_length: int = Field(default=1, ge=1)
    case_sensitive: bool = False
```

`src/piighost/config/models/placeholder.py`:

```python
class LabelHashPlaceholderConfig(_ComponentConfig):
    type: Literal["label_hash"]
    hash_length: int = Field(default=8, ge=4, le=64)
    salt: str = ""


class MaskPlaceholderConfig(_ComponentConfig):
    type: Literal["mask"]
    mask_char: str = Field(default="*", min_length=1, max_length=1)
    visible_chars: int = Field(default=4, ge=0)


class RedactCounterPlaceholderConfig(_ComponentConfig):
    type: Literal["redact_counter"]
    prefix: str = "REDACT"


class RedactHashPlaceholderConfig(_ComponentConfig):
    type: Literal["redact_hash"]
    hash_length: int = Field(default=8, ge=4, le=64)
    prefix: str = "REDACT"
    salt: str = ""


class RedactPlaceholderConfig(_ComponentConfig):
    type: Literal["redact"]
    value: str = "REDACT"
```

`src/piighost/config/models/detector.py`, on `RegexDetectorConfig`:

```python
    validators: dict[str, Literal["luhn", "iban", "nir"]] = Field(default_factory=dict)
```

The pepper is deliberately NOT configurable via TOML (a process secret does not belong in a config file); it stays on the `PIIGHOST_HASH_PEPPER` env var. Note this in the `salt` field docstrings.

- [ ] **Step 4: Update the `from_config` bodies**

`src/piighost/resolver/span.py`:
```python
    @classmethod
    def from_config(cls, cfg) -> "ConfidenceSpanConflictResolver":
        return cls(confidence_threshold=cfg.confidence_threshold)
```

`src/piighost/linker/entity.py`:
```python
    @classmethod
    def from_config(cls, cfg) -> "ExactEntityLinker":
        flags = re.RegexFlag(0) if cfg.case_sensitive else re.IGNORECASE
        return cls(flags=flags, min_text_length=cfg.min_text_length)
```

`src/piighost/placeholder.py`:
```python
# RedactPlaceholderFactory
        return cls(value=cfg.value)
# RedactCounterPlaceholderFactory
        return cls(prefix=cfg.prefix)
# RedactHashPlaceholderFactory
        return cls(prefix=cfg.prefix, hash_length=cfg.hash_length, salt=cfg.salt)
# LabelHashPlaceholderFactory
        return cls(hash_length=cfg.hash_length, salt=cfg.salt)
# MaskPlaceholderFactory
        return cls(mask_char=cfg.mask_char, visible_chars=cfg.visible_chars)
```

`src/piighost/detector/base.py`:
```python
from piighost.validators import validate_iban, validate_luhn, validate_nir

_VALIDATOR_REGISTRY: dict[str, Callable[[str], bool]] = {
    "luhn": validate_luhn,
    "iban": validate_iban,
    "nir": validate_nir,
}
```
```python
    @classmethod
    def from_config(cls, cfg: "RegexDetectorConfig") -> "RegexDetector":
        """Build a ``RegexDetector`` from its validated configuration."""
        validators = {
            label: _VALIDATOR_REGISTRY[name] for label, name in cfg.validators.items()
        }
        return cls(patterns=dict(cfg.patterns), validators=validators)
```

- [ ] **Step 5: Fix the strategy merge in `MaskPlaceholderFactory.__init__`** (code now matches the docstring)

```python
        merged = _build_default_strategies(mask_char, visible_chars)
        if strategies is not None:
            merged.update({k.lower(): v for k, v in strategies.items()})

        self._mask_char = mask_char
        self._strategies = merged
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/config/ -v && uv run pytest`
Expected: PASS. Also regenerate / eyeball the JSON schema: `uv run piighost schema | head -50`.

- [ ] **Step 7: Commit**

```bash
git add src/piighost/config src/piighost/resolver/span.py src/piighost/linker/entity.py src/piighost/placeholder.py src/piighost/detector/base.py tests/config/test_config_completeness.py
git commit -m "feat(config): expose thresholds, prefixes, salts, validators and mask options in TOML"
```

---

### Task 11: Dead code removal and docstring truth

**Files:**
- Modify: `src/piighost/pipeline/base.py`, `src/piighost/pipeline/thread.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Remove the dead `if self._cache is None` branches**

The constructor guarantees `self._cache = cache or SimpleMemoryCache()`, so the `None` checks in `_store_mapping`, `_cache_get_anon_result`, `_store_anon_result`, `_cached_detect`, `_cache_get` (base) and their thread overrides plus `override_detections` are unreachable. Delete each `if self._cache is None: return ...` block. In `override_detections`, also delete the `RuntimeError` raise and its docstring `Raises:` entry.

- [ ] **Step 2: Fix the lying docstrings**

- `AnonymizationPipeline` class + `cache` arg docstring: replace "If ``None``, no caching is performed and deanonymize will raise KeyError" with "If ``None``, a process-local ``SimpleMemoryCache`` is created; ``deanonymize`` needs the mapping to be present in this cache."
- `AnonymizationPipeline.deanonymize` docstring `Raises:` entry: `KeyError` → `CacheMissError`.
- `_replace_longest_first`, `MergeEntityConflictResolver`, `MaskPlaceholderFactory` docstrings were already aligned in Tasks 2, 4 and 10; verify with `grep -n "Union-Find\|KeyError" src/piighost/`.

- [ ] **Step 3: Update CLAUDE.md architecture section**

In the "Conversation Layer" paragraph: mention that memory is cache-backed (write-through snapshots, hydrated per call) and that `forget_thread()` purges a conversation entirely; note `cache_ttl` defaults to 3600 s. In the pipeline stage list, note the guard receives the emitted tokens. In "Design Patterns", note that config coupling is one-way (`config/builders.py` knows the components; core modules never import config).

- [ ] **Step 4: Run the full suite and lint**

Run: `uv run pytest && make lint`
Expected: PASS, no new lint errors.

- [ ] **Step 5: Commit**

```bash
git add src/piighost/pipeline CLAUDE.md
git commit -m "refactor(pipeline): drop unreachable cache-None branches; truthful docstrings"
```

---

### Task 12: Final verification

- [ ] **Step 1: Re-run the three original reproductions**

```bash
uv run python - <<'EOF'
import asyncio, warnings
warnings.filterwarnings("ignore")
from piighost.detector.base import ExactMatchDetector
from piighost.anonymizer import Anonymizer
from piighost.pipeline.thread import ThreadAnonymizationPipeline

async def main():
    det = ExactMatchDetector([("Patrick", "PERSON"), ("Alice", "PERSON"), ("Ali", "PERSON")])
    pipe = ThreadAnonymizationPipeline(detector=det, anonymizer=Anonymizer())
    a1, _ = await pipe.anonymize("Bonjour Patrick", thread_id="t")
    a2, _ = await pipe.anonymize("Alice est la", thread_id="t")
    assert a1 == "Bonjour <<PERSON:1>>", a1
    assert a2 == "<<PERSON:2>> est la", a2
    d = await pipe.deanonymize_with_ent("<<PERSON:1>> et <<PERSON:2>>", thread_id="t")
    assert d == "Patrick et Alice", d
    await pipe.anonymize("Ali est venu", thread_id="t2")
    out = pipe.anonymize_with_ent("Alibaba et Ali", thread_id="t2")
    assert out == "Alibaba et <<PERSON:1>>", out
    print("all reproductions fixed")

asyncio.run(main())
EOF
```
Expected: `all reproductions fixed`.

- [ ] **Step 2: Full suite, lint, no-extras import**

```bash
uv run pytest
make lint
uv run pytest tests/test_core_no_extras.py -v
```
Expected: all PASS, lint clean.

- [ ] **Step 3: Smoke-test against piighost-api (editable install)**

```bash
cd ~/PycharmProjects/piighost-api && make dev-local && uv run pytest -x -q || true
```
Expected: the consumer's suite still passes (it only uses `deanonymize_with_ent`, `load_pipeline`, and the middleware; all signatures are backward-compatible).

- [ ] **Step 4: Final commit if anything moved**

```bash
git status
git add -A && git commit -m "test: end-to-end verification of core overhaul" || echo "clean"
```

---

## Out of scope (explicitly deferred)

- Documentation pages under `docs/en/` + `docs/fr/` (forget API, TTL default, multi-worker story): separate pass with the piighost-docs conventions, after the code lands.
- `cz bump` / release and consumer pin updates: per repo policy, only when consumers need a published version.
- A Redis-native memory backend with atomic ops: the write-through snapshot is deliberately simple; revisit if conversation sizes make snapshots heavy.
