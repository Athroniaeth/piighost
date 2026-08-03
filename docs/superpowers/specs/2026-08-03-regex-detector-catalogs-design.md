# Regex Detector and Pattern Catalogs Design

Design spec for Spec A of the detector-adapters block of the PIIGhost v2 rewrite.
Internal design document, French prose, English code identifiers.

## Context

The v2 rewrite (`src/piighost/`) has the detector port `AnyDetector` and three
adapters so far, `ExactMatchDetector`, `ChunkedDetector`, and the test-only
matcher. The pluggable detectors from the blueprint (§4) are not ported yet.

This spec covers the first of three detector sub-projects, decided during
brainstorming:

- **Spec A (this document)** : `RegexDetector` + pattern catalogs +
  `CompositeDetector`. Pure Python, no optional dependency, fully unit-testable.
- Spec B (later) : `BaseNERDetector` + gliner2/spacy/transformers (integration).
- Spec C (later) : `LLMDetector`.

## Goal

Ship a pattern-based detector and a detector aggregator, plus reusable regex
catalogs, all pure Python and covered by unit and golden tests, without pulling
any optional dependency.

## Key decision: no checksum validators

Unlike v1, the `RegexDetector` ships with **no** Luhn / IBAN / NIR checksum
validators. Documents are often scanned via OCR (for example Mistral OCR), which
can mangle a single character. A checksum validator would then reject an
otherwise-real IBAN or NIR, and that value would leak unanonymized. For a PII
anonymization tool, over-detecting is safer than filtering-and-leaking. The
blueprint's earlier "checksum as confidence modulator (strict/lenient/off)" idea
is superseded by this. This rationale is to be surfaced when the docs are
updated.

Consequently `text/validators.py` (Luhn/IBAN/NIR) is out of scope, and the
catalog patterns that formerly relied on a validator (CREDIT_CARD, IBAN, NIR)
now match on shape alone.

## Components and files

- `src/piighost/components/detector/regex.py` : `RegexDetector`
- `src/piighost/components/detector/patterns/__init__.py` : re-exports the four
  catalog dicts
- `src/piighost/components/detector/patterns/generic.py` : `GENERIC_PATTERNS`
- `src/piighost/components/detector/patterns/us.py` : `US_PATTERNS`
- `src/piighost/components/detector/patterns/eu.py` : `EU_PATTERNS`
- `src/piighost/components/detector/patterns/fr.py` : `FR_PATTERNS`
- `src/piighost/components/detector/composite.py` : `CompositeDetector`
- `src/piighost/components/detector/__init__.py` : add the new public exports

Tests live under `tests/components/detector/`, none marked `integration` (no
extra is loaded).

## RegexDetector

Signature `__init__(self, patterns: dict[str, str])`, mapping a PII label to a
regex pattern string. Each pattern is compiled once at construction.

`async def detect(self, text: str) -> list[Detection]` iterates the compiled
patterns and, for every non-overlapping match, emits

```python
Detection(
    span=Span(match.start(), match.end()),
    text=match.group(),
    label=label,
    confidence=1.0,
)
```

Notes:

- No `validators` parameter (see the decision above).
- The signature is `async` to honor the `AnyDetector` port, but the body is
  synchronous. Regex matching is fast and CPU-cheap, so unlike the NER adapters
  it needs no `asyncio.to_thread` offload.
- The patterns carry their own `\b` boundaries where needed. `RegexDetector`
  adds no boundary wrapping; `ExactMatchDetector` is the boundary-aware matcher.
- Confidence is a flat `1.0` for every regex match, matching v1 behavior.
- Detections are returned in pattern-iteration order. Overlaps and duplicates
  are left to the span-conflict resolver stage, per the `AnyDetector` contract.

## Pattern catalogs

Ported verbatim from v1 (`src/v1_piighost/detector/patterns/`) as plain
`dict[str, str]` mapping label to pattern string:

- `GENERIC_PATTERNS` : `EMAIL`, `URL`, `IPV4`, `CREDIT_CARD`
- `US_PATTERNS` : `US_PHONE`, `US_SSN`, `US_ZIP`
- `EU_PATTERNS` : `IBAN`
- `FR_PATTERNS` : `FR_IBAN`, `FR_NIR`, `FR_PHONE`, `FR_SIRET`

Callers combine catalogs by dict merge, for example
`RegexDetector({**GENERIC_PATTERNS, **FR_PATTERNS})`. The `patterns/__init__.py`
re-exports the four dicts and lists them in `__all__`.

### Resilience requirement (trailing punctuation)

Each pattern must be resilient to adjacent punctuation and whitespace. An email
at the end of a sentence (`contact me at john@example.com.`), or followed by a
comma or a newline, must:

- still match despite the trailing character, and
- capture the value only, excluding the trailing `.`, `,`, or `\n`.

Any catalog pattern found to swallow adjacent punctuation, or to fail on it, is
fixed as part of this work. Two v1 patterns are corrected on this basis:

- `URL`, whose `[^\s<>"']+` tail swallowed a trailing `.`, `,`, or `)`. The tail
  is changed to require a final character that is not sentence punctuation.
- `US_PHONE`, whose leading `\b` failed to anchor before a `+` or `(`, so a
  `+1 (415) 555-2671` matched only from `1 (415) ...`, leaking the prefix. The
  anchor becomes a `(?<![\w+])` lookbehind plus a `(?!\d)` trailing lookahead.

This is verified by the golden tests below.

## CompositeDetector

Signature `__init__(self, detectors: list[AnyDetector])`.

`async def detect(self, text: str) -> list[Detection]` runs every child detector
concurrently via `asyncio.gather` and concatenates their results in detector
order. An empty detector list returns `[]` without awaiting anything.

No `mode`, per-detector confidence weight, or label allowlist (YAGNI, blueprint
§5). It does not deduplicate; overlapping detections flow to the span-conflict
resolver, matching the `AnyDetector` contract.

## Testing

All under `tests/components/detector/`, no model loaded, no `integration`
marker.

### RegexDetector unit tests

- exact offsets on a single match
- multiple matches of one pattern in a text
- multiple labels detected in one text
- empty text returns `[]`
- text with no match returns `[]`
- satisfies the `AnyDetector` runtime-checkable protocol (isinstance)

### Golden tests per catalog

The core of the resilience guarantee (blueprint §7). For each label:

- a set of **true positives** that must match
- a set of **true negatives** that must not match

Resilience cases, each canonical value tested first in isolation, then wrapped
in adjacent punctuation or whitespace: trailing comma (`"...com,"`), trailing
period (`"...com."`), trailing newline (`"...com\n"`), surrounded by spaces
(`" ...com "`), inside parentheses, and at the end of a sentence. Each such case
asserts the emitted `span` covers the value alone, with the trailing punctuation
excluded.

Anti-false-positive boundary cases, for example an email glued inside a larger
token, or a partial number, assert no detection.

### CompositeDetector tests

- merges detections from all children, detector order preserved
- runs children concurrently
- empty detector list returns `[]`
- satisfies the `AnyDetector` runtime-checkable protocol (isinstance)

## Out of scope

- Checksum validators and `text/validators.py`.
- `CompositeDetector` options beyond the plain list (mode, weights, allowlist).
- NER and LLM detectors (Specs B and C).
- Config models and builders for these detectors (config subsystem is a later
  block).
