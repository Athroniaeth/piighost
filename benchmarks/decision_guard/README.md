# Decision models as a guard rail after de-identification

This benchmark asks one question. After `piighost` has de-identified a text, can a second model tell whether personal data is still left in clear?

It compares two kinds of guard rail behind `piighost`'s `AnyGuardRail` port:

- a **decision model**, which answers yes or no with a probability and does not say where. Laya (Apache 2.0, the open counterpart of Jev) in its English and multilingual checkpoints, through `examples/guard_rail_laya.py` unchanged.
- a **span detector**, which returns the values it finds and where they are. GLiNER2 (`fastino/gliner2-privacy-filter-PII-multi` through `Gliner2PiiDetector`), re-run on the de-identified text.

`Gliner2GuardRail`, the GLiNER2 safety classifier that ships with `piighost`, is measured too. It answers "safe or unsafe" for the whole text, so it is a decision model as well.

Everything is synthetic and runs on CPU. Measured on 2026-10-06 and 07, `piighost` 2.0.1.

## Results

200 de-identified texts, 100 in French and 100 in English, half of them with one leak.

| Guard | AUROC | Leaks caught at 0.5 | False alarms at 0.5 | Original documents flagged at 0.5 | Median latency |
|---|---|---|---|---|---|
| Laya, English checkpoint | 0.50 | 69/100 | 60/100 | 33/100 | 708 ms |
| Laya, same, with a placeholder hint in the question | 0.52 | 81/100 | 81/100 | 27/100 | 744 ms |
| laya-multilingual | 0.50 | 81/100 | 81/100 | 47/100 | 390 ms |
| Laya, English checkpoint, same question as a two-option `choice` | 0.51 | 86/100 | 82/100 | 50/100 | 678 ms |
| `Gliner2GuardRail` | 0.61 | 11/100 | 3/100 | 23/100 | 330 ms |
| GLiNER2 spans, every detection | 0.84 | 100/100 | 100/100 | 100/100 | 402 ms |
| GLiNER2 spans, detections on placeholders ignored | 0.94 | 97/100 | 49/100 | 100/100 | 430 ms |

**Held out by template.** Texts of one template are alike, so the threshold is chosen on 27 templates and tested on the one left out, 28 times. The rule is to catch the most leaks with at most 5 % false alarms on the 27 templates. Summed over the 28 held-out templates, the span detector with placeholders ignored catches 83/100 leaks for 7/100 false alarms (cluster bootstrap 95 % intervals 73 to 92 % and 0 to 18 %). Laya's English checkpoint, under the same rule, catches 4/100 for 7/100, and 5/100 for 7/100 when the question is asked as a two-option `choice`. The raw span detector catches 60/100 for 7/100.

At a fixed 0.9 threshold, read off the same 200 texts, the span detector with placeholders ignored catches 83/100 leaks for 3/100 false alarms. That threshold was chosen on the test data, and the 3 false alarms are the three clean texts of one template, so this figure is optimistic.

- **Laya does not separate leaking texts from clean ones on this set.** Its AUROC is 0.50, chance level, in both languages, with both checkpoints and with both question types (cluster bootstrap 0.44 to 0.56, 0.45 to 0.58 for the `choice` form). Each leaking text has a clean twin. In a pair, the leaked value is replaced by a placeholder, and nothing else changes. The English checkpoint scores the leaking text higher in 54 pairs out of 100 and lower in 46 (sign test p = 0.48), and the mean gap is +0.007.
- **Placeholders raise Laya's score more than real personal data does.** In 85 of the 100 clean texts, the English checkpoint scored the de-identified version higher than the original document with every value in clear (sign test p = 5e-13, and 24 of the 28 templates go the same way, p = 0.0002). At 0.5 it flags 33 originals, so it misses 67 documents full of personal data, and 60 of their de-identified versions. Telling the model in the question that placeholders are not personal data does not help (AUROC 0.52).
- **A span detector reads the leak, and it can be told to ignore the placeholders because it says where it fired.** Raw, it tags `<<PERSON:1>>` as a person in 169 texts out of 200, and flags a placeholder in all 200, so it flags every text at 0.5. Its ranking is already far better than Laya's (AUROC 0.84, 0.78 to 0.90). With the detections that hold only placeholders dropped, which `DetectorGuardRail` does by default, its AUROC is 0.94 (0.90 to 0.98), and it scores the leaking text above its twin in 97 pairs out of 100 (one tie, two below, p = 2e-26). Its remaining false alarms are role words ("Customer", "[User]", "Tenant") and a civility next to a placeholder ("Mr `<<PERSON:3>>`").
- **Lowering the span detector's own threshold beats adding Laya.** Spans at 0.9 OR Laya at 0.9 catches the same 83 leaks, with 14 false alarms instead of 3. At lower Laya thresholds the OR rule catches more (95 leaks at Laya 0.5), but the span detector alone, at a lower threshold, catches as many with fewer false alarms every time: 95 for 32 against 95 for 60, 92 for 20 against 92 for 45, 89 for 14 against 89 for 32. The AND rules do no better than the span detector alone either.
- **`Gliner2GuardRail` misses the original documents too.** It flags 23 of the 100, every value in clear.

The full tables, by threshold from 0.1 to 0.9, language, leak type and placeholder count, with 95 % Wilson intervals, the held-out and cluster bootstrap figures, the paired tests, the reliability (calibration) bins and the latency, are in [results/report.md](results/report.md). The plots are in [results/plots/](results/plots/).

## The data

`generate.py` writes `data/texts.jsonl` (200 texts) and `data/twins.jsonl` (the clean twin of each leaking text).

1. **Source documents.** 14 templates per language (`templates.py`) cover emails, support chats, contracts, medical letters, HR notes, minutes and on-call rotas. Each is filled with fictitious values: names from fixed lists, emails built from them, random French phone numbers and UK numbers in Ofcom's drama ranges, IBANs with random digits and a valid checksum, NIR with a valid key, random NHS-style numbers, National Insurance numbers with the reserved `QQ` prefix, addresses on common street names.
2. **De-identification.** `piighost` de-identifies every source with an `AnonymizationPipeline` over an `ExactMatchDetector` given the generator's values (full name, first name and surname apart, emails, phones, IBAN, addresses, ID number) and the `merge` overlap resolver. The ground truth is therefore exact. A clean text has no value left in clear, by construction.
3. **Leaks.** In half the texts the detector is not given one value, or is given only part of it, or the source breaks the value in a way an exact match cannot follow. The nine leak types are below. A clean text with any value left, or a leaking text whose leak is missing or which leaks something else, is rejected and redrawn.

| Leak type | How it is made | Texts |
|---|---|---|
| `name` | a person's name, every mention left in clear | 12 |
| `variant` | the full name is masked, a later "Mme Dubois" or "Dr Carter" is not | 10 |
| `partial` | a first name next to a surname placeholder, or the tail of an IBAN after a placeholder | 10 |
| `email`, `phone`, `iban`, `address` | the value left in clear | 12 each |
| `id` | an NIR, NHS or National Insurance number left in clear | 10 |
| `split` | the value broken across two lines: after the @ of an email, inside an IBAN group, a hyphenated surname or street name | 10 |

A line break at a space would not leak, because `piighost` matches a space in a value against any run of whitespace, line breaks included.

Each record carries its language, genre, template, label, leak type and subtype, the leaked value and its offsets, the number of placeholders, the de-identified text and the source document. The texts run from 281 to 572 characters, under Laya's 512-token window (no text was truncated).

## Running it

```bash
uv run benchmarks/decision_guard/generate.py            # data/, deterministic (seed 20261006)
uv run benchmarks/decision_guard/run.py                 # every guard on the 200 texts
uv run benchmarks/decision_guard/run.py --twins         # every guard on the 100 clean twins
uv run benchmarks/decision_guard/run.py --sources       # every guard on the 100 original documents
uv run benchmarks/decision_guard/report.py              # results/report.md, summary.json, plots/
```

`run.py` takes guard names to run only some of them (`laya-en`, `laya-en-hint`, `laya-multi`, `laya-en-choice`, `gliner2-guard`, `gliner2-spans`, `gliner2-spans-ph`) and resumes where a run stopped. Each guard is called through its async `check()`, one text at a time, after a warm-up call. The checkpoints download on first use.

## The machine

A virtual machine with 16 vCPU (Intel Core, Haswell), 61 GB of RAM and no GPU, Linux 6.14, Python 3.13, PyTorch 2.14.1 on CPU with 16 threads, transformers 5.19.0, laya 0.3.28, gliner2 2.0.0. The machine also ran other services during the measurement (load average 9 to 15), so the latencies are an upper bound for this CPU.

## Limits

- **100 leaks and 100 clean texts.** The intervals in the report are wide, about ±10 points on a rate near 50 % (Wilson), and nearer ±18 once whole templates are resampled. Per leak type there are 10 to 12 texts.
- **Templates.** 28 templates filled about seven times each. A model may react to a template rather than to its content. The twin test, the held-out evaluation and the cluster bootstrap account for this, the per-threshold tables do not.
- **Thresholds across languages.** With the held-out rule, a threshold chosen on the French texts gives the span detector 43/50 leaks caught and 9/50 false alarms on the English ones (between 3 and 11 depending on where the threshold sits in the gap the French scores leave open). Chosen on English, it catches 27/50 French leaks. Choose the threshold on your own documents.
- **One question.** Laya is asked the question of `examples/guard_rail_laya.py`, as a yes/no (`noul`) question, with and without a placeholder hint, and as a two-option `choice`, the form Laya's model card recommends when `noul` answers look stuck. The `choice` form gives the same result (AUROC 0.51, twins 50 higher, 1 tie, 49 lower, sign test p = 1.0). Another wording, a few-shot calibration on in-house data, fine-tuning or the `laya-typed-decisions` checkpoint could do better. None was tried.
- **One placeholder style.** Every text uses `<<LABEL:N>>`. A decision model may read another style differently.
- **The leaks are the ones a pipeline makes when it misses a value.** A leak hidden on purpose, or a quasi-identifier (a rare job, a date and a town), is not measured.
- **Jev, Clef and OpenAI's Decisions API are not measured.** Jev and the Decisions API are hosted, and this benchmark sends nothing to a third party. Clef has open weights, but its smaller model is built on a 9B base, which was not tried on this CPU.
