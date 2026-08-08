---
icon: lucide/list-checks
---

# Roadmap

This page tracks what is still pending for `piighost`. Everything the v2 rewrite has shipped is documented in the rest of the site: pluggable detectors, entity linking and resolution, placeholder factories, the residual-PII guard, the Redis conversation memory with encrypted values, TOML and JSON configuration, the LangChain middleware, and OpenTelemetry observation.

!!! note "How to read this page"
    This roadmap is not a calendar commitment. It lists the items identified as still missing, not a promise to build them in order.

## Faker placeholder factory

The placeholder tag hierarchy has a realism axis, but no factory yet produces realistic values. A Faker factory would emit values that look real, such as a plausible name in place of `Patrick`{ .pii }, rather than a synthetic token like `<<PERSON:1>>`{ .placeholder }. It belongs under the label-preserving branch of the hierarchy, not the identity-preserving one: a Faker pool is finite, so two distinct people can draw the same fake name and a fake value can collide with a real one. That is why the factory carries no restoration guarantee and sits beside the masking factory rather than beside the counter and hash factories. See [Placeholder factories](placeholder-factories.md) for the current tag axes.

## Text normalization

A detector sees the text exactly as written. Accents, casing, spacing, or OCR noise can hide a value from a regex or shift a NER model's boundaries. A normalization stage would run before detection, feeding the detector a cleaned form while keeping an offset map back to the original text, so a span found on the normalized text can be remounted onto the raw text for replacement. The offset remounting is the hard part, since a normalization that inserts or drops characters no longer aligns one-to-one with the source.

## Optional result cache

The conversation memory caches each message's detections per thread, so resending a message inside a thread skips detection. There is no cache below the thread, so the same text sent under two different `thread_id` values is detected twice. An optional result cache keyed by text hash would let identical content skip detection regardless of thread, with a SQLAlchemy backend (aiosqlite for development, PostgreSQL for a shared deployment) as the persistent option beside the in-process one.

## See also

- [Placeholder factories](placeholder-factories.md): the current tag axes and factories.
- [Security](security.md): the threat model and the memory backend comparison.
- [Deploy a production pipeline](deployment.md): the Redis memory in production.
