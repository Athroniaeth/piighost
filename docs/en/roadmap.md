---
icon: lucide/list-checks
---

# Roadmap

This page tracks what is still pending for `piighost`, and the capabilities it deliberately leaves out. Everything the v2 rewrite has shipped is documented in the rest of the site: pluggable detectors, entity linking and resolution, placeholder factories, the residual-PII guard, the Redis conversation memory with encrypted values, TOML and JSON configuration, the LangChain middleware, and OpenTelemetry observation.

!!! note "How to read this page"
    This roadmap is not a calendar commitment. It lists the items identified as still missing, not a promise to build them in order.

## OpenAI-compatible proxy

`piighost` de-identifies inside an agent framework today, through the LangChain middleware or the Pydantic AI hooks. A proxy would move that protection to the HTTP boundary. `piighost-api` would expose an OpenAI-compatible endpoint, so an application changes only its `base_url` and needs no other code. On each `/v1/chat/completions` call the proxy anonymizes the messages, forwards the anonymized request to the real provider, deanonymizes the reply, and returns it in the OpenAI shape, so the provider never receives `Patrick`{ .pii }, only `<<PERSON:1>>`{ .placeholder }. The same proxy fronts any OpenAI-compatible endpoint, such as Azure OpenAI or a self-hosted server.

Three core pieces already exist for it. The conversation pipeline anonymizes and restores, the tool-boundary de-identification covers tool calls, and the streaming decoder rewrites a token split across server-sent-event chunks. The open questions are how a stateless request scopes its tokens, through a per-request thread or a thread-id header backed by the conversation memory, and how much of streaming and tool calls a first version covers.

Beyond the OpenAI wire format, the same de-identification core could sit behind several provider protocols, an `/v1` OpenAI route, an Anthropic Messages route, a Bedrock route, each a thin adapter over the shared pipeline, so an application keeps its native SDK and only points at the proxy.

## Text normalization

A detector sees the text exactly as written. Accents, casing, spacing, or OCR noise can hide a value from a regex or shift a NER model's boundaries. A normalization stage would run before detection, feeding the detector a cleaned form while keeping an offset map back to the original text, so a span found on the normalized text can be remounted onto the raw text for replacement. The offset remounting is the hard part, since a normalization that inserts or drops characters no longer aligns one-to-one with the source.

## Optional result cache

The conversation memory caches each message's detections per thread, so resending a message inside a thread skips detection. There is no cache below the thread, so the same text sent under two different `thread_id` values is detected twice. An optional result cache keyed by text hash would let identical content skip detection regardless of thread, with a SQLAlchemy backend (aiosqlite for development, PostgreSQL for a shared deployment) as the persistent option beside the in-process one.

## Wiring the streaming decoder

`AsyncPlaceholderStreamDecoder` already reassembles a token split across server-sent-event chunks, but nothing wires it into the integrations yet. A streamed reply arrives in fragments, so `<<PER`{ .placeholder } may land in one chunk and `SON:1>>`{ .placeholder } in the next, and a naive restore leaves the user seeing the broken token. Wiring the decoder into the LangChain middleware, the Pydantic AI hooks, and the future proxy would let each of them deanonymize a stream on the fly, buffering only across a token boundary and emitting restored text as it goes. It finishes an existing piece rather than building a new one, and it is a prerequisite for streaming through the proxy.

## Non-goals

Some capabilities were considered and left out on purpose. The reasoning is recorded here so the boundary is explicit. A future need that answers the caveat could revisit any of them.

- **Realistic surrogate placeholders (Faker).** A plausible fake reads naturally, but a finite fake pool collides. Two people can draw the same surrogate, and a fake can coincide with a real value, so the substitution is not reliably reversible. piighost keeps synthetic, collision-free tokens instead.
- **Encrypting the value into the token.** Restoration reads the token-to-value map from the conversation memory, not a self-contained ciphertext token. Embedding ciphertext makes a long token the model has to echo back verbatim, which it does unreliably.
- **Deterministic hashing of the value.** A keyed hash of a low-entropy value such as a name or an email is reversible by dictionary and leaks value equality across records. A value's token is already stable within a thread, and cross-corpus joins are not the target use case.
- **Blocking requests or deleting PII.** piighost secures PII by detecting and anonymizing it. Whether to refuse a request or erase a value is the caller's policy, decided from the detections piighost surfaces, not enforced here.
- **Value-transforming schemes, date shifting and format-preserving encryption.** piighost substitutes a detected span with a restorable token, not a transformed value. Date shifting sits outside that model, and the common FF3 and FF3-1 FPE schemes were withdrawn from the NIST standard.
- **Quasi-identifier detection.** A value like an age, a ZIP, or an appointment date identifies no one alone but can re-identify in combination, Sweeney found ZIP plus date of birth plus sex is near-unique. piighost detects and tokenizes identifiable values, not re-identifying combinations, because the only responses, generalizing the value or swapping in a fake, both transform it and are already out of scope.
- **Analytical privacy models (k-anonymity, l-diversity, t-closeness, differential privacy, synthetic data).** These protect a whole dataset released for analysis, generalizing or adding noise across every row at once. piighost protects a conversational stream one message at a time, and the generalization they rely on transforms the value, which is already out of scope.
- **Per-label placeholder routing.** One pipeline applies one placeholder factory to every entity. Routing by label, a counter for names but a mask for card numbers, is mechanically small but lowers the pipeline's tag guarantee to the weakest factory in the set and breaks the recognizable-identity guarantee the middleware relies on to restore. The gain did not justify muddying the tag design.
- **Multimodal de-identification.** piighost reads text. Detecting PII in an image or audio stream would mean OCR or transcription, then editing the pixels or samples, since a token cannot be placed back into an image the way it is into text. Redacting a region is a different problem with no reliable restoration, so it stays out of the text-substitution model.

The shape-only regex, with no checksum validation, is another deliberate non-goal. See [Limitations](limitations.md).

## See also

- [Placeholder factories](placeholder-factories.md): the current tag axes and factories.
- [Security](security.md): the threat model and the memory backend comparison.
- [Deploy a production pipeline](deployment.md): the Redis memory in production.
