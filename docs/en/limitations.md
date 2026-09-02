---
icon: lucide/triangle-alert
---

# Limitations

`piighost` de-identifies, it does not magically make a text safe. This page lists the known limitations, why they exist, and how to mitigate them. It extends the [threat model](security.md).

## Detectors are best-effort

A detector only finds what it knows how to recognize. Two families share the work, with different blind spots.

A pattern detector (`RegexDetector`) recognizes strings that follow a fixed structure, such as an email, an IP, or a credit-card shape. It is deterministic on those formats and blind to the rest. A NER detector (`Gliner2Detector`, `SpacyDetector`, `TransformersDetector`) or LLM detector (`LLMDetector`) recognizes free-form entities, a name, a place, an organization, but it misses some. A rare name, an unusual spelling, an out-of-distribution entity passes in cleartext to the LLM.

A PII that is not detected is not de-identified. This is an engineering concern, not a conceptual flaw.

**Mitigation**: chain a NER detector and a `RegexDetector` through the `CompositeDetector`, to cover both free-form text and structured formats. Load a locale-specific NER model for better accuracy. See [Extending PIIGhost](extending.md).

## A model can truncate a text longer than its context

A NER model has a maximum input length. A text longer than that is truncated by the model, and the truncated tail is never scanned, so its PII passes in cleartext. Nothing warns you by default.

**Mitigation**: set `max_chars` on the NER detector to the model's safe input length. With `auto_chunk` on (the default), a longer text is split into overlapping chunks scanned separately and remapped, so the tail is covered. With `auto_chunk` off, an over-long text raises `TextTooLongError` rather than being scanned in part. For very long inputs, wrap the detector in a `ChunkedDetector`.

## Language coverage is model-dependent

The set of languages a NER detector can cover is fixed by the model you plug in. Coverage varies from model to model, and not every language is supported equally. Before deploying on a new locale, read the model card and run a small validation set.

**Mitigation**: load a locale-specific model, or combine several detectors through the `CompositeDetector`.

## No checksum validation, by design

`RegexDetector` matches on shape alone. It verifies no checksum, no Luhn on cards, no IBAN check key, no NIR check key. This is deliberate.

A structured value can arrive mangled by OCR, one character misread. A checksum validator would then reject a real but mistranscribed IBAN or NIR, and that PII would pass in cleartext to the LLM. `piighost` prefers to keep a shape-level false positive rather than let a real damaged value leak. It is a security choice, failing toward the side that detects.

The trade-off is that `RegexDetector` can match strings that have the shape of a PII without being one (a digit run that looks like a card). The cost of such a false positive is benign, one extra token. The cost of the opposite false negative would be a leak.

**Mitigation**: refine the patterns if shape-level false positives disturb a precise workload. Do not reintroduce a checksum filter upstream of text that may come from OCR.

## Placeholders can collide depending on the factory

The placeholder factory decides what distinguishes two entities. Some families let two different values land on the same token.

- `RedactPlaceholderFactory` collapses every PII to `<<REDACT>>`{ .placeholder }. `LabelPlaceholderFactory` collapses every PII of one label to `<<PERSON>>`{ .placeholder }. Neither family distinguishes entities, so neither is reversible.
- `MaskPlaceholderFactory` keeps a fragment of the value, `j***@mail.com`{ .placeholder }. Two similarly shaped values can collide on one mask, and a mask can also collide with a real value in a tool response.
- `LabelCounterPlaceholderFactory` (`<<PERSON:1>>`{ .placeholder }) and `LabelHashPlaceholderFactory` (`<<PERSON:a1b2c3d4>>`{ .placeholder }) give a distinct token per entity and can be found again in text, so they stay reversible without ambiguity.

**Mitigation**: see [Placeholder factories](placeholder-factories.md) for the full taxonomy and the choice by use case.

## Deanonymization is only reliable under identity

Restoring a value from a placeholder assumes the placeholder identifies a unique entity. An identity-preserving factory (`LabelCounterPlaceholderFactory`, `LabelHashPlaceholderFactory`) guarantees that a token always lands on the same value. A collapsing factory (redact, label, mask) does not, so deanonymization becomes ambiguous or impossible.

The `PIIAnonymizationMiddleware` enforces this constraint at the type level. It requires a `PreservesRecognizableIdentity` factory, that is a token unique per entity and findable in text. A factory that does not meet that contract is rejected at construction (`UnrecognizableFactoryError`). The tool-call boundary relies on string replacement, so it needs unique tokens to stay reversible.

**Mitigation**: keep `LabelCounterPlaceholderFactory` or `LabelHashPlaceholderFactory` with the middleware. See [Tool-call strategies](tool-call-strategies.md) for the `FULL`, `INPUT`, `OUTPUT`, and `PASSTHROUGH` modes.

## PII invented by the LLM is not in the mapping

Restoration works on values seen at the input. If the LLM hallucinates a name that never appeared in the user's messages, for instance making up a plausible client name, that PII is in no mapping. It therefore cannot be tied back to an original value.

The middleware catches a neighbouring case, the invented placeholder. If the LLM fabricates a token that looks like a placeholder but was never emitted, `piighost` spots it (the token has no associated value) and refuses it by default (`InventedPlaceholderError`, the `RAISE` strategy). The `KEEP` and `DROP` strategies exist for other policies.

**Mitigation**: run a re-detection step on the LLM output at the application layer, and decide whether to strip, flag, or re-de-identify before display. A guard rail (`DetectorGuardRail`, `LLMGuardRail`, `ModerationGuardRail`) re-checks the de-identified output and flags residual PII, leaving the caller to raise `PIIRemainingError`.

## Memory is process-local by default

`InMemoryConversationMemory` keeps the mapping thread by thread in a process-local dictionary. Nothing survives a restart, nothing is shared across processes. As soon as you scale horizontally, two workers have two memories and two independent placeholder spaces, so the same entity can get two different tokens depending on which worker handles it.

**Mitigation**: configure `RedisConversationMemory` to share the mapping across workers and make it survive a restart. That backend can encrypt the values and hash the keys (opt-in, all-or-nothing). The in-memory backend can be bounded with `max_threads` and `ttl` to cap its growth in a long-lived process. See [Security](security.md) and [Deployment](deployment.md).

## A thread isolates the mapping

Memory is partitioned by `thread_id`. Two separate conversations share no placeholder, which is intended, but implies that the same person in two threads gets two unrelated tokens. The middleware requires a `thread_id` and does not fall back to a shared default thread, to prevent one conversation from seeing another's mapping.

**Mitigation**: propagate a stable per-conversation `thread_id`. Call `forget_thread` to purge a conversation from memory once it no longer has reason to exist.

## Latency overhead is not yet benchmarked

There is no official benchmark of the latency added by the pipeline on typical workloads. The overhead depends on the detector (NER inference), the text length, and whether values are already known in the thread's memory.

**Mitigation**: measure on your own workload before sizing production traffic. Keep detectors on GPU when possible for NER-heavy paths.

## Minimum viable threat coverage

`piighost` addresses exfiltration *toward the LLM and its provider*. It does not replace encryption at rest, access control, or secure logging practices for the rest of your system. See [Security](security.md) for the full threat model.
