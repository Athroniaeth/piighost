---
icon: lucide/gauge
---

# Detection, measured

How many confidential values a configured `piighost` pipeline hides, and what each stage adds over calling a NER model directly. The figures come from a benchmark run on 2026-09-29 on five data sets, English and French, with `piighost` 1.10.0.

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
| Generated deeds | 36 → 95 | 19 → 90 |
| Long generated deeds | 2 → 96 | 1 → 95 |
| TAB | 27 → 46 | 31 → 61 |
| PARHAF | 15 → 61 | 11 → 61 |
| Gretel finance | 66 → 79 | 55 → 75 |

The French sets run the `fr-notarial` config, TAB runs `support-en`. The published `fr-notarial` scores what its F rung scores. On every set and for both models, the 95 % intervals of A and F do not overlap.

!!! warning "The deed formulae were tuned on generated deeds, then checked on official templates"
    The rules that catch a name after "Monsieur" or an address after "demeurant" were written against the dev seed of the generated deeds, so part of their gain may come from the generator's phrasing. A control set measures it: 112 official documents, twelve Code du travail numérique models and the two leases of décret n° 2015-587, their blanks filled with fictitious values. There the full pipeline hides 91 % of direct identifiers with GLiNER2 and 86 % with ONNX, 3 to 4 points below the generated deeds. The rules alone lose 18 points, from 70 to 53 %. Precision falls to 43 %, since the model tags role nouns of the official prose ("salarié", "entreprise") and the expander repeats them.

## Where the gain comes from

On the generated deeds with GLiNER2, rung by rung: 36 % for A, 66 % for B, 94 % for D, 95 % for E and F.

- **Chunking** gives 31 to 33 points on the generated deeds and 53 to 64 on the long ones. A model reads a fixed window, and without chunking it never sees past it. On the long deeds, rung A only reads page one and misses every value after it.
- **The regex rules** give 28 to 40 points. They carry every value with a fixed shape, emails, IBANs, social security numbers, company numbers, phones and dates reach 100 %, where the model alone finds at most a fifth of them. The formulae of a deed ("Monsieur", "Maître", "née", "demeurant", "section") catch the names and addresses the model misses.
- **The word-boundary expander** adds 1 to 3 points, less than before, since the rules now find most repeats themselves.
- **The entity resolver** adds no recall. It groups the spellings of one person onto one token.

Rules and the model often flag the same value with different lengths. `fr-notarial` keeps their union with the `merge` overlap resolver. With the default `confidence` resolver, a rule's short span at confidence 1.0 beat a model's longer one, and on the finance set names fell from 89 to 77 %.

Precision, the share of masked text that was really a value, stays near 86 % on the generated deeds. On the long deeds the expander drops it to 59 % with ONNX, since a heading word masked once is then masked everywhere.

## What still leaks

On the generated deeds, full GLiNER2 pipeline:

| Category | Hidden | Documents with none left in clear |
|---|---|---|
| Email, IBAN, social security number, company number, phone, date of birth | 100 % | 100 % |
| Person | 95 % | 59 % |
| Organisation | 94 % | 88 % |
| Address | 94 % | 81 % |
| Cadastral parcel | 43 % | 75 % |

43 % of the generated deeds come out with nothing left in clear, against none before the date and deed rules. A single forgotten name is still enough to spoil a deed. The cadastral parcels a table lists without the word "section" are missed.

## What the benchmark changed

Each run found something, fixed in the library or in the hub's `fr-notarial` before the next.

- **`piighost` 1.9.0.** The word-boundary expander could add an occurrence inside a kept detection, and the render stage then raised `OverlappingSpansError`, on 163 of the 200 generated deeds. French phones typeset with no-break spaces were never matched. An email with accented letters was matched from its first ASCII run. A detector config could not set `max_chars`, so a config-built model read a whole deed in one pass and ran out of memory past 13,000 characters.
- **Dates.** A date of birth is a direct identifier, and neither model of the benchmark was asked for one, so the rules carry it. `fr-notarial` hides every French date, since a pattern cannot tell a date of birth from the date of the deed, but spares the date of a numbered legal text ("loi n° 89-462 du 6 juillet 1989").
- **Deed formulae.** A name after a civility or "Maître", a maiden name after "née", an address after "demeurant" or "situé", a street address, a lieu-dit and a cadastral reference after "section".
- **`SWIFT_BIC`.** It matched any run of eight or eleven capitals. It now needs a keyword or a digit, so a heading such as "DESIGNATION" stays in clear.
- **`piighost` 1.10.0.** The `merge` overlap resolver, so a rule's short span no longer uncovers part of the model's.

On the generated deeds, GLiNER2, run after run:

| | 1.9.0 candidate | Dates, chunking | Formulae, merge |
|---|---|---|---|
| Direct identifiers hidden, full pipeline | 76 % | 82 % | 95 % |
| The config as published | 63 % | 82 % | 95 % |
| Deeds with nothing left in clear | 0 % | 2.5 % | 43 % |
| Precision | 77 % | 78 % | 86 % |
| Capitalised headings masked, of 1,437 | 411 | 411 | 30 |
| Legal references masked, of 452 | 14 | 250 | 14 |

These patterns belong to a document config. A chat config should not hide every date nor read "Monsieur" as the start of a name to hide.

## Limits of these numbers

- The French documents are mostly generated. A hand-written medical set (PARHAF) scores lower than the generated one, and no open notarial deed exists to check the generated deeds against.
- Each figure comes from one run on CPU. The intervals account for the choice of documents, not for another model version.
- The model calls are the same across runs, replayed from a cache keyed by their exact input. A change in a figure comes from the pipeline or the config, never from a different inference.

## See also

- [Limitations](limitations.md): what detection cannot promise, whatever its score.
- [Pre-built detectors](examples/detectors.md): the regex catalogs of the hub and the models.
- [TOML reference](configuration/toml.md): `max_chars` and the detector keys.
