---
icon: lucide/triangle-alert
---

# Limitations

`piighost` de-identifies, it does not magically make a text safe. This page lists the known limitations, why they exist, and how to mitigate them. It extends the [threat model](security.md).

## Detectors are best-effort

A detector only finds what it knows how to recognize. Two families share the work, with different blind spots.

A pattern detector (`RegexDetector`) recognizes strings that follow a fixed structure, such as an email, an IP, or a credit-card shape. It is deterministic on those formats and blind to the rest. A NER detector (`Gliner2Detector`, `SpacyDetector`, `TransformersDetector`) or LLM detector (`LLMDetector`) recognizes free-form entities (a name, a place, an organization), but it misses some. A rare name, an unusual spelling, an out-of-distribution entity passes in cleartext to the LLM.

Confidential data that is not detected is not de-identified. This is an engineering concern, not a conceptual flaw.

**Mitigation**: chain a NER detector and a `RegexDetector` through the `CompositeDetector`, to cover both free-form text and structured formats. Load a locale-specific NER model for better accuracy. See [Extending PIIGhost](extending.md).

## A model can truncate a text longer than its context

A NER model has a maximum input length. The model truncates a longer text. The truncated tail is never scanned, so its PII passes in cleartext. Nothing warns you by default.

The limit belongs to the model, not to the pipeline. It applies to any de-identification backed by a NER model. `piighost` ships the means to work around it rather than live with it.

**Mitigation**: set `max_chars` on the NER detector to the model's safe input length. With `auto_chunk` on (the default), a longer text is split into overlapping chunks. Each chunk is scanned separately, then the results are remapped, so the tail is covered. With `auto_chunk` off, an over-long text raises `TextTooLongError` rather than being scanned in part. For very long inputs, wrap the detector in a `ChunkedDetector`.

## Language coverage is model-dependent

The set of languages a NER detector can cover is fixed by the model you plug in. Coverage varies from model to model, and not every language is supported equally. Before deploying on a new locale, read the model card and run a small validation set.

Here too the limit belongs to the model, not to the pipeline. A pattern detector does not have this limit, because an IBAN or an email address has the same shape in every language.

**Mitigation**: load a locale-specific model, or combine several detectors through the `CompositeDetector`.

## Whole-word search assumes spaces between words

To find a value again, `piighost` searches it as a whole word, so `Jean`{ .pii } is not found inside `Jeanne`{ .pii }. A value must not touch a letter, a digit or a hyphen on either side. Chinese, Japanese and Thai write words without spaces between them. A value in those scripts therefore always touches a letter, and it is never found.

| Text | Searched value | Found |
|---|---|---|
| `Jeanne et Jean`{ .pii } | `Jean`{ .pii } | the second `Jean`{ .pii } |
| `田中さんは田中です`{ .pii } | `田中`{ .pii } | nothing |

Three components rely on this search. `ExactMatchDetector` finds nothing. `WordBoundaryExpander` finds no repetition. `LLMDetector` places in the text each value the LLM names, so it drops a value the LLM did find, and that value is sent as it is. The detectors that return offsets, `RegexDetector` and the NER detectors, are not affected.

Supporting these scripts would take a word segmenter per language, and the pipeline has none.

**Mitigation**: on Chinese, Japanese or Thai text, detect with a NER model or a pattern rather than with `ExactMatchDetector` or `LLMDetector`, and do not count on the expander for repetitions.

## A pattern cannot cover every script at once

Python's `re` has no word segmentation. It also does not count combining marks as letters, for example the vowel signs of Hindi and the other Indic scripts. An email pattern therefore has to choose which letters it takes in, and each choice leaves some letters out.

| Text | Pattern taking Unicode letters, `(?u:\w)` | `EMAIL` of `hub:piighost/generic` |
|---|---|---|
| `écrire à expéditeur@exemple.fr`{ .pii } | `expéditeur@exemple.fr`{ .pii } | `expéditeur@exemple.fr`{ .pii } |
| `メールはtanaka@example.jpです`{ .pii } | the whole sentence | `tanaka@example.jp`{ .pii } |
| `ελένη@example.gr`{ .pii } | `ελένη@example.gr`{ .pii } | nothing |
| `राम@उदाहरण.भारत`{ .pii } | nothing | nothing |

A pattern that takes Unicode letters in finds an accented or a Greek address whole. In Chinese or Japanese text with no space around the address, the ideographs next to it are letters too, so the pattern takes them in. The token hides more than the address, and nothing is sent in clear. The Hindi address still escapes it, since its vowels are combining marks.

The `EMAIL` pattern of `hub:piighost/generic` takes Latin letters only, that is the ASCII letters and digits plus the Latin range `À` to `ɏ`. It finds the accented and the Japanese examples exactly. It misses every address written in another script, and that address is sent as it is.

**Mitigation**: for text in non-Latin scripts, detect addresses with a NER model, or write in your config an email pattern suited to the addresses that text really holds. A pattern written inline in the config overrides the group's pattern on the same label.

## No checksum validation (deliberate)

`RegexDetector` matches on shape alone. It verifies no checksum, no Luhn on cards, no IBAN check key, no NIR check key. This is deliberate.

A structured value can arrive mangled by OCR, one character misread. A checksum validator would then reject a real but mistranscribed IBAN or NIR, and that PII would pass in cleartext to the LLM. `piighost` prefers to keep a shape-level false positive rather than let a real damaged value leak. It is a security choice. When the detector is wrong, it errs on the side of detecting too much.

The trade-off is that `RegexDetector` can match strings that have the shape of a PII without being one (a digit run that looks like a card). The cost of such a false positive is benign, one extra token. The cost of a false negative, a real PII left undetected, would be a leak.

**Mitigation**: refine the patterns if shape-level false positives disturb a precise workload. Do not reintroduce a checksum filter upstream of text that may come from OCR. If your inputs are typed and never go through OCR, the trade-off flips. You can then write your own detector with checksum validation, because the `AnyDetector` port is open. See [Extending PIIGhost](extending.md).

## Placeholders can collide depending on the factory

The placeholder factory decides what distinguishes two entities. Some families produce the same output for two different inputs.

- `RedactPlaceholderFactory` collapses every value to `<<REDACT>>`{ .placeholder }. `LabelPlaceholderFactory` collapses every value of one label to `<<PERSON>>`{ .placeholder }. Neither family distinguishes entities, so neither is reversible.
- `MaskPlaceholderFactory` keeps a fragment of the value, `j***@mail.com`{ .placeholder }. Two similarly shaped values can collide on one mask, and a mask can also collide with a real value in a tool response.
- `LabelCounterPlaceholderFactory` (`<<PERSON:1>>`{ .placeholder }) and `LabelHashPlaceholderFactory` (`<<PERSON:a1b2c3d4>>`{ .placeholder }) give a distinct token per entity, which can be found again in text. They therefore stay reversible without ambiguity.

**Mitigation**: see [Placeholder factories](placeholder-factories.md) for the full taxonomy and the choice by use case.

## Restoration is only reliable under identity

Restoring a value from a placeholder assumes the placeholder identifies a unique entity. Two properties combine in the token. **Typing** says which kind of value it is (a person, a location, an email). **Identity** says which one it is among those of the same kind. Each factory carries a preservation tag that declares what its token keeps of these two properties.

| Factory | Preservation tag | Token emitted | Typing | Identity | Restoration |
|---|---|---|---|---|---|
| `RedactPlaceholderFactory` | `PreservesNothing` | `<<REDACT>>`{ .placeholder } | no | no | impossible |
| `LabelPlaceholderFactory` | `PreservesLabel` | `<<PERSON>>`{ .placeholder } | yes | no | impossible |
| `MaskPlaceholderFactory` | `PreservesShape` | `j***@mail.com`{ .placeholder } | yes | partial | ambiguous |
| `LabelCounterPlaceholderFactory` | `PreservesLabeledIdentityOpaque` | `<<PERSON:1>>`{ .placeholder } | yes | yes | reliable |
| `LabelHashPlaceholderFactory` | `PreservesLabeledIdentityOpaque` | `<<PERSON:a1b2c3d4>>`{ .placeholder } | yes | yes | reliable |

On `Patrick and Marie live in Paris`{ .pii }, the difference shows immediately.

- With `LabelPlaceholderFactory`, both people become the same `<<PERSON>>`{ .placeholder }. The type is there, the identity is not, so nothing says which of the two tokens was `Patrick`{ .pii }.
- With `LabelCounterPlaceholderFactory`, `Patrick`{ .pii } becomes `<<PERSON:1>>`{ .placeholder } and `Marie`{ .pii } becomes `<<PERSON:2>>`{ .placeholder }. Each token maps to a single value, so restoration is unambiguous.

The `PIIAnonymizationMiddleware` enforces this constraint at the type level. It requires a `PreservesRecognizableIdentity` factory, that is a token unique per entity and findable in text. A factory that does not meet that contract is rejected at construction (`UnrecognizableFactoryError`). The tool-call boundary needs unique tokens to stay reversible, because it relies on string replacement.

**Mitigation**: keep `LabelCounterPlaceholderFactory` or `LabelHashPlaceholderFactory` with the middleware. See [Tool-call strategies](tool-call-strategies.md) for the `FULL`, `INPUT`, `OUTPUT`, and `PASSTHROUGH` modes.

## PII invented by the LLM is not in the mapping

Restoration works on values seen at the input. If the LLM hallucinates a name that never appeared in the user's messages, for instance making up a plausible client name, that PII is in no mapping. It therefore cannot be tied back to an original value.

The middleware catches a neighbouring case, the invented placeholder. If the LLM fabricates a token that looks like a placeholder but was never emitted, `piighost` spots it (the token has no associated value) and refuses it by default (`InventedPlaceholderError`, the `RAISE` strategy). The `KEEP` and `DROP` strategies exist for other policies.

**Mitigation**: run a re-detection step on the LLM output at the application layer, and decide whether to strip, flag, or re-de-identify before display. A guard rail (`DetectorGuardRail`, `LLMGuardRail`, `ModerationGuardRail`) re-checks the de-identified output and flags residual confidential data. The pipeline then raises `PIIRemainingError`.

## Memory is process-local by default

`InMemoryConversationMemory` keeps the mapping thread by thread in a process-local dictionary. Nothing survives a restart, nothing is shared across processes. As soon as you scale horizontally, two workers have two memories and two independent placeholder spaces. The same entity can therefore get two different tokens depending on which worker handles it.

**Mitigation**: configure `RedisConversationMemory` to share the mapping across workers and make it survive a restart. That backend can encrypt the values and hash the keys (opt-in, all-or-nothing). The in-memory backend is bounded by default. In a long-lived process, `max_threads` and `ttl` adjust the cap on its growth. See [Security](security.md) and [Deployment](deployment.md).

## A thread isolates the mapping

Memory is partitioned by `thread_id`. Two separate conversations share no placeholder. This is intended, but the same person then gets two unrelated tokens in two threads. The middleware requires a `thread_id` and does not fall back to a shared default thread, to prevent one conversation from seeing another's mapping.

**Mitigation**: propagate a stable per-conversation `thread_id`. Call `forget_thread` to purge a conversation from memory once it no longer has reason to exist.

## Latency overhead is not yet benchmarked

There is no official benchmark of the latency added by the pipeline on typical workloads. The overhead depends on the detector (NER inference), the text length, and whether values are already known in the thread's memory.

**Mitigation**: measure on your own workload before sizing production traffic. Keep detectors on GPU when possible for NER-heavy paths.

## Minimum viable threat coverage

`piighost` addresses exfiltration *toward the LLM and its provider*. It does not replace encryption at rest, access control, or secure logging practices for the rest of your system. See [Security](security.md) for the full threat model.
