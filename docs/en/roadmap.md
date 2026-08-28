---
icon: lucide/list-checks
---

# Roadmap

This page tracks what is still pending for `piighost`, and the capabilities it deliberately leaves out. Everything the v2 rewrite has shipped is documented in the rest of the site: pluggable detectors, entity linking and resolution, placeholder factories, the residual-PII guard, the Redis conversation memory with encrypted values, TOML and JSON configuration, the LangChain middleware, and OpenTelemetry observation.

!!! note "How to read this page"
    This roadmap is not a calendar commitment. It lists the items identified as still missing, not a promise to build them in order.

## ~~OpenAI-compatible proxy~~

~~Shipped in `piighost-api`: an OpenAI-compatible endpoint under `/openai/v1` where an application changes only its `base_url`, names the real upstream in a header, and the proxy anonymizes each request, forwards it, and deanonymizes the reply. The HTTP concern lives in `piighost-api`, not this library.~~

## Optional result cache

The conversation memory caches each message's detections per thread, so resending a message inside a thread skips detection. There is no cache below the thread, so the same text sent under two different `thread_id` values is detected twice. An optional result cache keyed by text hash would let identical content skip detection regardless of thread, with a SQLAlchemy backend (aiosqlite for development, PostgreSQL for a shared deployment) as the persistent option beside the in-process one.

## ~~Wiring the streaming decoder~~

~~Now wired: `AsyncPlaceholderStreamDecoder` reaches the integrations through `TextDeidentifier.deanonymize_stream`, exposed on the LangChain middleware as `deanonymize_stream` and used by the Anthropic proxy in `piighost-api`. An app wraps it around its own streaming loop to deanonymize a reply on the fly, buffering only across a token boundary. Any factory also builds the raw decoder over its grammar with `async_stream_decoder`, for another framework.~~

## Configuration hub

A pipeline is fully described by a TOML or JSON file, but every user rebuilds that description by hand. A configuration hub would let a user pull a ready-to-use configuration by a short identifier and run it directly, the way a prompt hub distributes prompts. The library already has the pieces it stands on, `load_config`, `load_pipeline`, and `load_thread_pipeline` parse and build a pipeline from a file. The missing part is distribution, a registry to publish and fetch a configuration by identifier, version pinning to a piighost release, and a trust boundary, since a configuration is declarative data rather than code. A catalogue of per-profession configurations, notaries, accountants, a general-purpose default, would grow on top of it over time.

This is planned as a separate project rather than part of the `piighost` core, since it is a distribution service, not a pipeline concern.

## ~~Agent-harness integration~~

~~Now shipped for Claude Code through its hook system: `piighost.integrations.claude_code` anonymizes the prompt and tool outputs and restores tool inputs, driving a thin client to `piighost-api`. See [De-identify Claude Code with hooks](examples/claude-code.md). The OpenAI-compatible proxy in `piighost-api` still covers any harness that lets an application change its `base_url`; an Anthropic-compatible proxy endpoint also ships in `piighost-api` for harnesses that speak Anthropic's Messages API, beside the hooks, reusing the same de- and re-anonymization, streaming reassembly, and tool-boundary handling already in the core.~~

## Local in-browser document app (WebAssembly)

A document-anonymization web app that runs entirely in the browser, so a regulated professional can de-identify a client file without any data leaving the machine, answers the confidentiality and consent constraints raised repeatedly around client data. The engine already exists, the project website runs the real piighost in the browser through Pyodide, with in-browser GLiNER detection, so the library itself needs no reimplementation. What remains is the application around it, client-side document parsing (PDF, DOCX) and OCR, a review step where the user validates or completes the anonymization, and a share step. This is a separate application built on the library, not a library feature.

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
- **Tamper-evident audit logging.** A hash-chained, append-only log of de- and re-anonymization events, where a deleted or edited entry becomes detectable, is an accountability feature for a multi-user or hosted deployment, not for the library. It belongs to `piighost-api` or `piighost-chat`, where an actor, a store, and a trust boundary exist. Access control on an append-only sink is the primary defence, and chaining only adds value when the store's custodian is not trusted or a third party needs portable proof. The library surfaces the events; recording them tamper-evidently is the deployment's concern.

The shape-only regex, with no checksum validation, is another deliberate non-goal. See [Limitations](limitations.md).

## See also

- [Placeholder factories](placeholder-factories.md): the current tag axes and factories.
- [Security](security.md): the threat model and the memory backend comparison.
- [Deploy a production pipeline](deployment.md): the Redis memory in production.
