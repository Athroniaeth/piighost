---
icon: lucide/gauge
---

# Detection, measured

How many confidential values a configured `piighost` pipeline hides, and what each stage adds over calling a NER model directly. The figures come from a benchmark run on 2026-09-27 on five data sets, English and French.

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
| Generated deeds | 36 → 76 | 19 → 70 |
| Long generated deeds | 2 → 79 | 1 → 86 |
| TAB | 27 → 46 | 31 → 61 |
| PARHAF | 15 → 34 | 11 → 32 |
| Gretel finance | 66 → 77 | 55 → 73 |

On every set and for both models, the 95 % intervals of A and F do not overlap.

## Where the gain comes from

On the generated deeds with GLiNER2, rung by rung: 36 % for A, 66 % for B, 74 % for D, 76 % for E and F.

- **Chunking** does most of it, 31 to 33 points on the generated deeds and 53 to 64 on the long ones. A model reads a fixed window, and without chunking it never sees past it. On the long deeds, rung A only reads page one and misses every value after it.
- **The regex rules** add 8 to 14 points, and they carry every value with a fixed shape. Emails, IBANs, social security numbers, company numbers and phones reach 100 %, where the model alone finds at most a fifth of them.
- **The word-boundary expander** adds 2 to 4 points on the generated deeds and 10 to 11 on the long ones, where a name appears again pages later.
- **The entity resolver** adds no recall. It groups the spellings of one person onto one token, which lowers the share of people split across several tokens, at the price of a few people merged by mistake.

The pipeline costs some precision, the share of masked text that was really a value. On the generated deeds it falls from 87 % for A to 77 % for F. Part of the cost comes from capitalised headings the `SWIFT_BIC` pattern takes for bank codes. On the long deeds the expander drops it to 53 % with ONNX, since a heading word masked once is then masked everywhere.

## What still leaks

On the generated deeds, full GLiNER2 pipeline:

| Category | Hidden | Documents with none left in clear |
|---|---|---|
| Email, IBAN, social security number, company number, phone | 100 % | 100 % |
| Organisation | 86 % | 77 % |
| Person | 83 % | 13 % |
| Address | 57 % | 27 % |
| Cadastral parcel | 0 % | 0 % |
| Date of birth | 0 % | 0 % |

No generated deed comes out with nothing left in clear, and a single forgotten name is enough. The fixed-shape values are solved by rules. Dates of birth and cadastral parcels were targeted by no detector of the measured configs. Names and addresses depend on the model.

## What the benchmark changed

A first run found defects that `piighost` 1.9.0 fixes.

- The word-boundary expander could add an occurrence inside a kept detection, and the render stage then raised `OverlappingSpansError`. That happened on 163 of the 200 generated deeds.
- French phones typeset with no-break spaces were never matched, which held phone recall between 50 and 72 %. It is now 100 %.
- An email address with accented letters was matched from its first ASCII run, leaving the start in clear.
- A detector config could not set `max_chars`, so a config-built model read a whole deed in one pass. The published `fr-notarial` lost 13 points of recall to it, and ran out of memory past 13,000 characters.

Closing the date-of-birth gap means hiding every date, since a pattern cannot tell a date of birth from the date of the deed. A deed config can afford that, a chat config cannot. The configs measured above carry no date pattern.

## Limits of these numbers

- The French documents are mostly generated. A hand-written medical set (PARHAF) scores lower than the generated one, and no open notarial deed exists to check the generated deeds against.
- Each figure comes from one run on CPU. The intervals account for the choice of documents, not for another model version.
- The measured library is the release candidate of 1.9.0 (commit `eb1a963`). The release adds a faster word-boundary search with the same matches, and the `max_chars` config key.

## See also

- [Limitations](limitations.md): what detection cannot promise, whatever its score.
- [Pre-built detectors](examples/detectors.md): the regex catalogs and the models.
- [TOML reference](configuration/toml.md): `max_chars` and the detector keys.
