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
