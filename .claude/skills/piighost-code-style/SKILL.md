---
name: piighost-code-style
description: Use when writing or refactoring PIIGhost Python code (src/ or tests/). Captures the project's code conventions and idioms BEYOND what PEP8 and ruff enforce: preferred expression forms, dispatch patterns, naming, and structural preferences the maintainer has called out during review. ruff/PEP8 handle formatting; this skill handles taste.
---

# PIIGhost code style

## Overview

PEP8 and ruff already enforce formatting (line length, import order, quotes,
trailing commas). This skill captures the conventions that tooling does **not**
enforce: how the maintainer prefers expressions, dispatch, and naming to be
written. They are taste rules, gathered from review feedback.

Apply them whenever you write or refactor code. When a rule conflicts with an
established local pattern, match the surrounding code and flag the tension
rather than rewriting silently.

**This skill grows.** When the maintainer states a new preference during a
review, add it here as a new numbered rule with an `Avoid -> Prefer` pair and a
one-line *why*. Keep the existing entries; do not renumber on every edit.

## Rules

### 1. Prefer a named local + `or` over a `None`-guard ternary

When falling back to a default and the falsy-but-not-`None` edge (e.g. the empty
string) is irrelevant, bind a named local with `or` instead of an inline
`x if x is not None else y`.

Avoid:
```python
return {"text": redact_as if redact_as is not None else self.text, ...}
```

Prefer:
```python
text = redact_as or self.text
return {"text": text, ...}
```

Why: the named local reads like a sentence and `or` is shorter. Only keep
`is not None` when an empty/zero value must be preserved distinctly from the
default, and add a comment saying so when you do.

### 2. Prefer a data-driven dict over an if/elif dispatch cascade

When selecting one of N things by a key, use a dict lookup, not a chain of
`if key == ...: return ...`. A dict is O(1), auditable at a glance, and adding a
case is a single line.

Avoid:
```python
def _resolve_lazy_detector(key):
    if key == "lazy:gliner2":
        from piighost.detector.gliner2 import Gliner2Detector
        return Gliner2Detector
    if key == "lazy:spacy":
        from piighost.detector.spacy import SpacyDetector
        return SpacyDetector
    raise KeyError(key)
```

Prefer:
```python
_LAZY_DETECTORS: dict[str, tuple[str, str]] = {
    "lazy:gliner2": ("piighost.detector.gliner2", "Gliner2Detector"),
    "lazy:spacy": ("piighost.detector.spacy", "SpacyDetector"),
}

def _resolve_lazy_detector(key):
    module_path, class_name = _LAZY_DETECTORS[key]
    return getattr(importlib.import_module(module_path), class_name)
```

Why: removes the repetition, and missing-key handling comes for free (dict
access already raises `KeyError`). When the targets are optional-dependency
modules, map to a `(module, name)` tuple and resolve with
`importlib.import_module` so only the requested one is imported and the lazy
behavior is preserved.

### 3. A repeated magic string becomes a named constant

When the same literal (a sentinel value, a default key, a prefix) appears in
more than one place, especially across modules, give it a name. A typo in one
copy then fails loudly instead of silently diverging.

Avoid:
```python
# thread.py
_current_thread_id = ContextVar("...", default="default")
def anonymize(self, text, thread_id="default"): ...
# middleware.py
return "default"
```

Prefer:
```python
# thread.py
DEFAULT_THREAD_ID = "default"
_current_thread_id = ContextVar("...", default=DEFAULT_THREAD_ID)
def anonymize(self, text, thread_id=DEFAULT_THREAD_ID): ...
# middleware.py
from piighost.pipeline.thread import DEFAULT_THREAD_ID
return DEFAULT_THREAD_ID
```

Why: one source of truth, and the constant's docstring is the place to explain
the value's meaning and caveats.

### 4. Safety-sensitive defaults fail closed, not open

A default that silently shares state or relaxes a guarantee is a footgun. When
omitting a parameter could leak data or merge unrelated contexts, the default
should refuse (raise) rather than fall back to a shared/permissive value. Keep
the permissive path available as an explicit opt-in.

Avoid:
```python
def __init__(self, ..., require_thread_id: bool = False): ...
# omitting thread_id silently routes every conversation to a shared bucket
```

Prefer:
```python
def __init__(self, ..., require_thread_id: bool = True): ...
# missing thread_id raises; pass require_thread_id=False to opt into the
# shared-default behavior knowingly
```

Why: the dangerous case (cross-conversation PII leakage) should be impossible
by accident. A named shared fallback (see rule 3, `DEFAULT_THREAD_ID`) can
still exist, but reaching it is a deliberate choice, documented as
single-conversation / stateless use.

### 5. Order-preserving dedup is `dict.fromkeys`, not a manual seen-set

To deduplicate a sequence while keeping first-seen order, use
`dict.fromkeys` (the stdlib idiom for hashable items). Do not hand-roll a
`seen` set plus an output list. `itertools` is the wrong tool here: it has no
order-preserving `unique`, and `groupby` only collapses *consecutive* equals.

Avoid:
```python
seen, out = set(), []
for d in items:
    if d not in seen:
        seen.add(d)
        out.append(d)
```

Prefer:
```python
out = list(dict.fromkeys(items))
```

### 6. Variants sharing a skeleton use Template Method, not copy-pasted bodies

When several subclasses run the same overall sequence but differ on one step,
put the skeleton on the base once and let subclasses override only the varying
hook. Do not copy the whole method into each subclass.

Avoid: `MergeResolver.resolve` and `FuzzyResolver.resolve` each re-implementing
group then merge then sort.

Prefer:
```python
class MergeResolver:
    def resolve(self, items):
        return self._merge_and_sort(self._group(items))   # skeleton, shared
    def _group(self, items): ...                          # the only hook

class FuzzyResolver(MergeResolver):
    def _group(self, items): ...                          # override just this
```

Why: the shared steps (merge, sort) live in one place; a subclass declares only
what makes it different.

### 7. Config -> component: forward fields generically, customize only to transform

A component built from config whose field names match its constructor
parameters needs no `from_config`: a generic builder forwarding
`cfg.model_dump(exclude={"type", "name"})` as kwargs covers it. Write a custom
`from_config` (or builder branch) **only** when construction transforms a field
(rename, wrap, registry lookup) or loads a resource (a model, a sub-component).

Avoid: a `from_config` on every component that just copies fields
(`return cls(value=cfg.value)`).

Prefer: delete the trivial ones, keep a single generic `_construct`; reserve
`from_config` for the transforming cases (e.g. `ExactEntityLinker` mapping
`case_sensitive` to `flags`, detectors loading a model).

Trade-off to keep in mind: the generic path couples config field names to
constructor parameter names implicitly (checked at runtime, not statically).
It is worth it when the convention already holds uniformly; flag it when it
does not.

### 8. Docstrings carry no markup except bullet lists

Docstrings are plain prose. The only formatting allowed is bullet lists. No
inline-code backticks, no RST roles (`:class:`, `:func:`), no emphasis
(`*word*`), no headers, tables, or code fences. Identifiers and code fragments
are written bare, in the flow of the sentence.

Avoid:
```python
"""A :class:`Span` is a half-open interval ``[start, end)`` over *text*."""
```

Prefer:
```python
"""A Span is a half-open interval [start, end) over the text."""
```

Why: the maintainer reads docstrings as source, not rendered output, so markup
is noise without payoff. Google-style `Args`/`Returns`/`Raises` sections are
structure, not markup, and stay; a bullet list is fine when enumerating.

### 9. Typing is complete: parameterize generics, use builtin forms

Annotations are mandatory (ruff ANN) AND complete. Fill in every generic's
parameters, and use the PEP 585 builtin generics rather than the deprecated
`typing` aliases. On the 3.11+ codebase `type[Exception]` needs no import, while
`typing.Type`/`Dict`/`List` do and are deprecated.

Avoid:
```python
from typing import Dict, Type

mapping: Dict[Type, Type] = {}    # deprecated aliases
def f(cls: type) -> None: ...     # bare, unparameterized
```

Prefer:
```python
mapping: dict[type[Exception], type[Exception]] = {}
def f(cls: type[Exception]) -> None: ...
```

Why: a bare `type` or `list` says no more than `Any`. Parameterizing states
intent and lets pyrefly catch misuse; builtin generics drop the import and match
the 3.11+ target. This complements the mandatory-annotation config.

### 10. Target 3.11+ natively: no `from __future__ import annotations`

The runtime floor is Python 3.11, so write native typing directly: `Self`,
`X | Y` unions, builtin generics. Do not add `from __future__ import
annotations`.

Avoid:
```python
from __future__ import annotations

def overlaps(self, other: "Span") -> bool: ...
```

Prefer:
```python
from typing import Self

def overlaps(self, other: Self) -> bool: ...
```

Why: 3.11 evaluates these annotations natively. The future import adds noise and
changes annotation semantics (strings instead of objects) for no gain here. Use
`Self` for self-references; a rare forward reference to a later class uses a
quoted name.

### 11. One exception subclass per failure mode, under a shared base

Every library error descends from a single base (`PIIGhostError`). Give each
distinct failure its own subclass rather than a generic error or one class with
a mode flag. A caller then catches the base for the whole family or a subclass
for one case.

Avoid:
```python
if start < 0 or end <= start:
    raise ValueError("bad span")      # generic, one message for two failures
```

Prefer:
```python
if start < 0:
    raise NegativeSpanStartError(...)
if end <= start:
    raise SpanOrderingError(...)       # both subclass SpanError -> PIIGhostError
```

Why: callers catch broadly (`except PIIGhostError`) or narrowly (`except
SpanOrderingError`) without matching on message strings.

### 12. Tests are data-driven: a constant declares cases, parametrize runs them

Declare the cases in a module-level constant and drive them with
`pytest.mark.parametrize`. Do not write one near-identical test per case, and do
not discover cases by runtime introspection.

Avoid:
```python
def test_span_error() -> None: assert issubclass(SpanError, PIIGhostError)
def test_negative() -> None: assert issubclass(NegativeSpanStartError, SpanError)
# ...one function per class, or an inspect.getmembers() discovery helper
```

Prefer:
```python
EXCEPTION_HIERARCHY: dict[type[Exception], type[Exception]] = {
    SpanError: PIIGhostError,
    NegativeSpanStartError: SpanError,
}

@pytest.mark.parametrize(("error", "parent"), EXCEPTION_HIERARCHY.items())
def test_error_has_expected_direct_parent(
    error: type[Exception], parent: type[Exception]
) -> None:
    assert error.__bases__ == (parent,)
```

Why: adding a case is one line in the constant, the data is auditable at a
glance, and referencing the symbols in the constant also guards their names.
Explicit data beats introspection: it is readable and fails on the exact case.

### 13. Every test has a one-line docstring; regression tests name the breaking change

Each test function carries a one-line docstring stating what it verifies, even
when the method name is descriptive. A test under `tests/regression/` phrases it
as the breaking change it guards against. Let a real failure propagate rather
than wrapping it; do not add try/except tolerance for a case that does not exist
yet, and do not leave debug prints.

Avoid:
```python
def test_every_module_imports_cleanly() -> None:
    for m in walk():
        print(m)                        # debug leftover
        try:
            import_module(m.name)
        except ImportError as exc:      # tolerance for a case that does not exist
            if "install piighost[" not in str(exc):
                raise
```

Prefer:
```python
def test_every_module_imports_cleanly() -> None:
    """Check that no module fails to import (syntax error, circular import)."""
    for m in walk():
        import_module(m.name)           # a real ImportError fails the test
```

Why: the docstring documents intent; a propagated error gives the true
traceback; speculative tolerance is dead code (YAGNI), added only when the case
becomes real.

### 14. Class docstrings document data fields in Attributes, not Args

Follow the Google Python Style Guide for classes. The class docstring documents
its public data attributes in an `Attributes:` section (same format as a
function's `Args:`), and NOT its properties, which the guide explicitly excludes
and which are documented on the property itself. Reserve `Args:` for functions
and methods. For a frozen dataclass the fields are the attributes, so they go
under `Attributes:`; construction failures go under `Raises:`.

Avoid:
```python
class Detection:
    """...

    Args:
        span: ...
    Attributes:
        label: ...   # a property; does not belong here
    """
```

Prefer:
```python
class Detection:
    """...

    Attributes:
        span: ...          # a data field
    Raises:
        ConfidenceError: ...
    """

    @property
    def label(self) -> str:
        """The PII label."""   # documented on the property itself
```

Why: matches the Google guide, which says public attributes "excluding
properties" go in `Attributes` and reserves `Args` for `__init__` and
functions. It also avoids duplicating a field across `Args` and `Attributes`.

### 15. Bind a constructed value to a named local, do not nest it in a call

When building or transforming a value to pass it on, give it a name on its own
line rather than nesting the construction inside another call. And keep a
multi-argument constructor call exploded, one argument per line with a trailing
comma, so the construction stays visible and diffs cleanly.

Avoid:
```python
detections.append(replace(detection, span=detection.span.shift(chunk.start)))
d = Detection(span=Span(0, 4), label="PERSON", confidence=0.9, text="Emma")
```

Prefer:
```python
span = detection.span.shift(chunk.start)
remapped = replace(detection, span=span)
detections.append(remapped)

span = Span(0, 4)
d = Detection(
    span=span,
    label="PERSON",
    confidence=0.9,
    text="Emma",
)
```

Why: each construction gets a name and a line, so the data flow reads top to
bottom instead of hiding inside an argument list. Applies to building data (an
object, a dataclass, a transformed value), not to every trivial subexpression
like `f(x + 1)`.
