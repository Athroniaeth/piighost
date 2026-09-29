---
icon: lucide/gauge
---

# Detection, measured

How many confidential values a configured `piighost` pipeline hides, and what each stage adds over calling a NER model directly. The figures come from a benchmark run on 2026-09-29 on five data sets, English and French, with `piighost` 1.9.0.

!!! note "A strict count"
    A value counts as hidden only when every one of its characters is masked. A partial mask is a leak: `Paul <<PERSON:1>>`{ .placeholder } leaves `Paul`{ .pii } in clear, so it counts as a miss for `Paul Lemoine`{ .pii }. This is stricter than the overlap match NER papers report, and the numbers are lower for it.

## The question

A NER model finds names, places and organisations. `piighost` wraps one in a pipeline that adds chunking, regex rules, a search for repeats and entity grouping. Does that pipeline hide more than the model alone, and which stage does the work?

To answer it, the benchmark adds one stage at a time, with the same model on the same documents.

| Rung | System |
|---|---|
| A | the model called directly on the whole text, as a developer would, cut at its window |
| B | A, with `piighost`'s chunking |
| C | the regex rules of the config, no model |
| D | B and C together, overlaps resolved |
| E | D, plus the word-boundary expander |
| F | E, plus the entity resolver, the full config |

Two models run the ladder: GLiNER2 (`fastino/gliner2-multi-v1`, the model of the `fr-notarial` hub config) and `onnx-community/gliner_multi_pii-v1` in ONNX through `BridgeDetector`, the engine that runs in the browser.

## The data

| Set | Language | Documents | What it is | Caution |
|---|---|---|---|---|
| Generated deeds | French | 200 | deeds, leases, employment contracts, emails, medical reports, built from templates with fictitious values | generated text flatters: the values sit where a slot is |
| Long generated deeds | French | 12 | the same, from 2 to 60 pages | three documents per length, wide intervals |
| TAB | English | 127 | ECHR judgments annotated for anonymisation (Pilán et al., 2022) | public judgments a model may have seen in training |
| PARHAF | French | 101 | medical reports written by hand by medical residents for fictitious patients | almost no fixed-shape identifier, so it tests the model |
| Gretel finance | French | 443 | synthetic finance documents | written by an LLM |

No set contains a real private person's data. Only direct identifiers are scored in the headline. TAB and PARHAF also mark quasi-identifiers (a date, a profession, a family status), which are reported apart and never averaged in.

## Results

Direct identifiers hidden, model alone (A) then full pipeline (F), in %.

| Set | GLiNER2 A → F | ONNX A → F |
|---|---|---|
| Generated deeds | 36 → 82 | 19 → 76 |
| Long generated deeds | 2 → 80 | 1 → 87 |
| TAB | 27 → 46 | 31 → 61 |
| PARHAF | 15 → 60 | 11 → 58 |
| Gretel finance | 66 → 78 | 55 → 74 |

The French sets run the `fr-notarial` config, TAB runs `support-en`. The published `fr-notarial` scores what its F rung scores, now that it chunks its model.

On every set and for both models, the 95 % intervals of A and F do not overlap.

## Where the gain comes from

On the generated deeds with GLiNER2, rung by rung: 36 % for A, 66 % for B, 80 % for D, 82 % for E and F.

- **Chunking** does most of it, 31 to 33 points on the generated deeds and 53 to 64 on the long ones. A model reads a fixed window, and without chunking it never sees past it. On the long deeds, rung A only reads page one and misses every value after it.
- **The regex rules** add 11 to 19 points, and they carry every value with a fixed shape. Emails, IBANs, social security numbers, company numbers and phones reach 100 %, where the model alone finds at most a fifth of them.
- **The word-boundary expander** adds 2 to 4 points on the generated deeds and 10 to 11 on the long ones, where a name appears again pages later.
- **The entity resolver** adds no recall. It groups the spellings of one person onto one token, which lowers the share of people split across several tokens, at the price of a few people merged by mistake.

The pipeline costs some precision, the share of masked text that was really a value. On the generated deeds it falls from 87 % for A to 78 % for F. Part of the cost comes from capitalised headings the `SWIFT_BIC` pattern takes for bank codes. On the long deeds the expander drops it to 54 % with ONNX, since a heading word masked once is then masked everywhere.

## What still leaks

On the generated deeds, full GLiNER2 pipeline:

| Category | Hidden | Documents with none left in clear |
|---|---|---|
| Email, IBAN, social security number, company number, phone, date of birth | 100 % | 100 % |
| Organisation | 86 % | 77 % |
| Person | 83 % | 13 % |
| Address | 57 % | 27 % |
| Cadastral parcel | 0 % | 0 % |

Only 2.5 % of the generated deeds come out with nothing left in clear, since a single forgotten name is enough. The fixed-shape values and the dates are solved by rules. Cadastral parcels are targeted by no detector yet. Names and addresses depend on the model.

## What the benchmark changed

The first runs found defects that `piighost` 1.9.0 fixes.

- The word-boundary expander could add an occurrence inside a kept detection, and the render stage then raised `OverlappingSpansError`. That happened on 163 of the 200 generated deeds.
- French phones typeset with no-break spaces were never matched, which held phone recall between 50 and 72 %. It is now 100 %.
- An email address with accented letters was matched from its first ASCII run, leaving the start in clear.
- A detector config could not set `max_chars`, so a config-built model read a whole deed in one pass. The published `fr-notarial` lost 13 points of recall to it, and ran out of memory past 13,000 characters.

A date of birth is a direct identifier no NER model tags, and no measured config hid one. The hub's `fr-notarial` now hides every French date, since a pattern cannot tell a date of birth from the date of the deed, and chunks its model at `max_chars = 1000`. Against the previous run:

| Generated deeds, GLiNER2 | Before | After |
|---|---|---|
| Direct identifiers hidden, full pipeline | 76 % | 82 % |
| The config as published | 63 % | 82 % |
| Dates of birth hidden | 0 % | 100 % |
| Deeds with nothing left in clear | 0 % | 2.5 % |
| Precision | 77 % | 78 % |

On PARHAF, where identifying dates are direct identifiers, the full pipeline goes from 34 to 60 %. The cost is in the traps. The dates inside legal references are masked too, so "loi du 10 juillet 1965" loses its date, in 239 of the 452 planted references against 3 before. A chat config should not carry these patterns.

## Limits of these numbers

- The French documents are mostly generated. A hand-written medical set (PARHAF) scores lower than the generated one, and no open notarial deed exists to check the generated deeds against.
- Each figure comes from one run on CPU. The intervals account for the choice of documents, not for another model version.
- The model calls are the same across runs, replayed from a cache keyed by their exact input. A change in a figure comes from the pipeline or the config, never from a different inference.

## See also

- [Limitations](limitations.md): what detection cannot promise, whatever its score.
- [Pre-built detectors](examples/detectors.md): the regex catalogs and the models.
- [TOML reference](configuration/toml.md): `max_chars` and the detector keys.
