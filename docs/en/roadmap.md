---
icon: lucide/list-checks
---

# Roadmap

This page tracks what is still pending for `piighost`, and the capabilities it deliberately leaves out. Everything the v2 rewrite has shipped is documented in the rest of the site. That covers pluggable detectors, entity linking and resolution, placeholder factories, the guard for residual confidential data, the Redis conversation memory with encrypted values, TOML and JSON configuration, the LangChain middleware, and OpenTelemetry observation.

!!! note "How to read this page"
    This roadmap is not a calendar commitment. It lists the items identified as still missing, not a promise to build them in order.

## ~~OpenAI-compatible proxy~~

~~Shipped in `piighost-api`, as an OpenAI-compatible endpoint under `/openai/v1`. An application changes only its `base_url` and names the real upstream in a header. The proxy de-identifies each request, forwards it, and restores the reply. The HTTP handling lives in `piighost-api`, not this library. See [De-identify an OpenAI client with the proxy](examples/openai-proxy.md).~~

## Optional result cache

The conversation memory caches each message's detections per thread, so resending a message inside a thread skips detection. No cache is shared across threads, so the same text sent under two different `thread_id` values is detected twice. An optional result cache, keyed by the hash of the text, would let identical content skip detection regardless of thread. A SQLAlchemy backend (aiosqlite for development, PostgreSQL for a shared deployment) would be its persistent option, beside the in-process one.

## ~~Wiring the streaming decoder~~

~~Now wired, `AsyncPlaceholderStreamDecoder` reaches the integrations through `TextDeidentifier.deanonymize_stream`. The LangChain middleware exposes that method as `deanonymize_stream`, and the Anthropic proxy in `piighost-api` uses it. An app wraps `deanonymize_stream` around its own streaming loop to restore a reply on the fly, buffering only across a token boundary. For another framework, any factory also builds the raw decoder over its grammar with `async_stream_decoder`.~~

## ~~Configuration catalog~~

~~Now shipped as a separate project, the [piighost catalog](https://catalog.piighost.dev) publishes reviewed pattern groups and whole pipeline configurations under a short identifier, each pinned by commit. A regex detector pulls a group through `catalogs`. `load_config`, `load_pipeline`, `load_thread_pipeline` and `piighost --config` take a reference such as `catalog:piighost/fr-notarial` to run a configuration directly.~~

## ~~Agent-harness integration~~

~~Now shipped for Claude Code, through its hook system. `piighost.integrations.claude_code` de-identifies the prompt and tool outputs, and restores tool inputs. It drives a thin client to `piighost-api`. See [De-identify Claude Code with hooks](examples/claude-code.md). The OpenAI-compatible proxy in `piighost-api` still covers any harness that lets an application change its `base_url`. Beside the hooks, `piighost-api` also ships an Anthropic-compatible proxy endpoint, for harnesses that speak Anthropic's Messages API. That proxy reuses what the core already does, that is de-identification and restoration, streaming reassembly, and tool-boundary handling. See [De-identify Claude Code with the Anthropic proxy](examples/anthropic-proxy.md).~~

## Local in-browser document app (WebAssembly)

A document-de-identification web app that runs entirely in the browser answers the confidentiality and consent constraints raised repeatedly around client data. With it, a regulated professional can de-identify a client file without any data leaving the machine. The engine already exists. The project website runs the real `piighost` in the browser through Pyodide, with GLiNER detection in the browser too. The library itself therefore needs no reimplementation. What remains to build is the application around it. It includes client-side document parsing (PDF, DOCX) and OCR, a review step where the user validates or completes the de-identification, and a share step. This is a separate application built on the library, not a library feature.

## Non-goals

Some capabilities were considered and left out on purpose. The reasoning is recorded here so the boundary is explicit. Any of them could be revisited if a future need answers the reason it was left out.

- **Realistic surrogate placeholders (Faker).** A plausible fake reads naturally, but a finite fake pool collides. Two people can draw the same surrogate, and a fake can coincide with a real value, so the substitution is not reliably reversible. `piighost` keeps synthetic, collision-free tokens instead.
- **Encrypting the value into the token.** Restoration reads the token-to-value map from the conversation memory, not a self-contained ciphertext token. Embedding ciphertext makes a long token the model has to echo back verbatim. The model does that unreliably.
- **Deterministic hashing of the value.** A keyed hash of a low-entropy value such as a name or an email is reversible by dictionary and leaks value equality across records. A value's token is already stable within a thread, and cross-corpus joins are not the target use case.
- **Blocking requests or deleting confidential data.** `piighost` secures confidential data by detecting and de-identifying it. Whether to refuse a request or erase a value is the caller's policy, decided from the detections `piighost` surfaces, not enforced here.
- **Value-transforming schemes, date shifting and format-preserving encryption.** `piighost` substitutes a detected span with a restorable token, not a transformed value. Date shifting sits outside that model, and the common FF3 and FF3-1 FPE schemes were withdrawn from the NIST standard.
- **Quasi-identifier detection.** A value like an age, a ZIP, or an appointment date identifies no one alone, but can re-identify a person in combination. Sweeney found ZIP plus date of birth plus sex is near-unique. `piighost` detects and tokenizes identifiable values, not re-identifying combinations. Against a combination, the only responses are to generalize the value or to swap in a fake. Both transform the value, and are already out of scope.
- **Analytical privacy models (k-anonymity, l-diversity, t-closeness, differential privacy, synthetic data).** These protect a whole dataset released for analysis, generalizing or adding noise across every row at once. `piighost` protects a conversational stream one message at a time. These models also rely on generalization, which transforms the value and is therefore already out of scope.
- **Per-label placeholder routing.** One pipeline applies one placeholder factory to every entity. Routing by label, for example a counter for names and a mask for card numbers, is mechanically small. But it lowers the pipeline's tag guarantee to that of the weakest factory in the set. Routing also breaks the recognizable-identity guarantee the middleware relies on to restore. The gain did not justify muddying the tag design.
- **Multimodal de-identification.** `piighost` reads text. Detecting confidential data in an image or audio stream would mean OCR or transcription, then editing the pixels or samples, since a token cannot be placed back into an image the way it is into text. Redacting a region is a different problem, with no reliable restoration. Redaction therefore stays out of the text-substitution model.
- **Tamper-evident audit logging.** A tamper-evident log is a hash-chained, append-only log of de-identification and restoration events, where a deleted or edited entry becomes detectable. It is an accountability feature for a multi-user or hosted deployment, not for the library. It belongs to `piighost-api` or `piighost-chat`, where an actor, a store, and a trust boundary exist. Access control on an append-only sink is the primary defence. Chaining only adds value when whoever holds the store is not trusted, or when a third party needs portable proof. The library surfaces the events. Recording them tamper-evidently is the deployment's concern.

The shape-only regex, with no checksum validation, is another deliberate non-goal. See [Limitations](limitations.md).

## See also

- [Placeholder factories](placeholder-factories.md): the current tag axes and factories.
- [Security](security.md): the threat model and the memory backend comparison.
- [Deploy a production pipeline](deployment.md): the Redis memory in production.
