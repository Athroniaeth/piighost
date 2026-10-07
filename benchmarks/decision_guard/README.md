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
| `Gliner2GuardRail` | 0.61 | 11/100 | 3/100 | 23/100 | 330 ms |
| GLiNER2 spans, every detection | 0.84 | 100/100 | 100/100 | 100/100 | 402 ms |
| GLiNER2 spans, detections on placeholders ignored | 0.94 | 97/100 | 49/100 | 100/100 | 356 ms |

At 0.9, the span detector with placeholders ignored catches 83/100 leaks for 3/100 false alarms.

- **Laya does not separate leaking texts from clean ones on this set.** Its AUROC is 0.50, chance level, in both languages and with both checkpoints. Each leaking text has a clean twin that differs only by the leak, replaced by a placeholder. The English checkpoint scores the leaking text higher in 54 pairs out of 100 and lower in 46, and the mean gap is +0.007.
- **Placeholders raise Laya's score more than real personal data does.** On the 100 original documents, every name, email and IBAN in clear, the English checkpoint says yes in 33. On the same documents after de-identification, it says yes in 60. Telling the model in the question that placeholders are not personal data does not help (AUROC 0.52).
- **A span detector reads the leak, and it can be told to ignore the placeholders because it says where it fired.** Raw, it tags every `<<PERSON:1>>` as a person and flags every text. With the detections that hold only placeholders dropped, its AUROC is 0.94, and it scores the leaking text above its twin in 97 pairs out of 100 (one tie, two below). Its remaining false alarms are role words ("Customer", "[User]", "Tenant") and a civility next to a placeholder ("Mr `<<PERSON:3>>`").
- **Adding Laya to the span detector adds false alarms and no leak.** Spans at 0.9 OR Laya at 0.9 catches the same 83 leaks, with 14 false alarms instead of 3.

The full tables, by threshold from 0.1 to 0.9, language, leak type and placeholder count, with 95 % Wilson intervals, the reliability (calibration) bins and the latency, are in [results/report.md](results/report.md). The plots are in [results/plots/](results/plots/).

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

`run.py` takes guard names to run only some of them (`laya-en`, `laya-en-hint`, `laya-multi`, `gliner2-guard`, `gliner2-spans`, `gliner2-spans-ph`) and resumes where a run stopped. Each guard is called through its async `check()`, one text at a time, after a warm-up call. The checkpoints download on first use.

## The machine

A virtual machine with 16 vCPU (Intel Core, Haswell), 61 GB of RAM and no GPU, Linux 6.14, Python 3.13, PyTorch 2.14.1 on CPU with 16 threads, transformers 5.19.0, laya 0.3.28, gliner2 2.0.0. The machine also ran other services during the measurement (load average 9 to 15), so the latencies are an upper bound for this CPU.

## Limits

- **100 leaks and 100 clean texts.** The intervals in the report are wide, about ±10 points on a rate near 50 %. Per leak type there are 10 to 12 texts.
- **Templates.** 28 templates filled about seven times each. A model may react to a template rather than to its content. The twin test controls for this, the other figures do not.
- **One question.** Laya is asked the question of `examples/guard_rail_laya.py`, and a variant with a placeholder hint. Another wording, a few-shot calibration on in-house data or the `laya-typed-decisions` checkpoint could do better. None was tried.
- **One placeholder style.** Every text uses `<<LABEL:N>>`. A decision model may read another style differently.
- **The leaks are the ones a pipeline makes when it misses a value.** A leak hidden on purpose, or a quasi-identifier (a rare job, a date and a town), is not measured.
- **Jev, Clef and OpenAI's Decisions API are not measured.** Jev and the Decisions API are hosted, and this benchmark sends nothing to a third party. Clef has open weights, but its smaller model is built on a 9B base, which was not tried on this CPU.
