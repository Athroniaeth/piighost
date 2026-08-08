---
icon: lucide/message-circle-question
---

# FAQ

??? question "Is it really necessary to de-identify PII before calling an LLM?"
    Yes, and this holds regardless of `piighost`. The stakes (exfiltration to providers, legal requisition, training on conversations, GDPR compliance, data leaks) are covered in [Why de-identify?](../why-anonymize.md). The page is library-agnostic: it explains why the problem exists before justifying a solution like `piighost`.

??? question "Which languages are supported?"
    It depends entirely on the detector you plug in. The pipeline itself is language-agnostic. With a `gliner2` detector and a multilingual GLiNER2 model, you get about 100 languages out of the box. With a `spacy` detector, whatever spaCy supports. With a `regex` detector, language is irrelevant. See [Extending PIIGhost](../extending.md) for the detector catalogue.

??? question "Which entities are detected out of the box?"
    None. `piighost` does not ship its own NER model, this is a deliberate design choice. You bring the detector. Use an `exact` detector for fixed dictionaries, a `regex` detector with a prebuilt catalog (`generic`, `us`, `eu`, `fr`) or your own patterns, a `gliner2` detector for open NER (`PERSON`, `LOCATION`, `ORGANIZATION`, `EMAIL`, any label you ask for), or compose them with a `composite` detector.

??? question "Does the regex detector validate checksums (Luhn, IBAN, NIR)?"
    No, by design. A checksum validator rejects a value whose digits do not compute, which is exactly what OCR noise or a typo produces. Rejecting it would leak the PII it was meant to catch. The `regex` detector matches on shape alone and errs toward over-detection, which is the safe direction for de-identification. If you need to narrow a match, add a stricter pattern rather than a validator.

??? question "How do I configure a pipeline?"
    Write a TOML or JSON file describing each stage, then load it. `load_pipeline` builds a stateless pipeline, `load_thread_pipeline` builds a thread pipeline with a conversation memory, and the file suffix picks the parser. Every section and component `type` is in the [configuration reference](../configuration/toml.md). The `config` extra is required (`pip install piighost[config]`).

??? question "What latency does the pipeline add?"
    The pipeline itself is on the millisecond scale (regex and lookups). The real cost comes from the detector. GLiNER2 on CPU for a 200-token message is typically 50 to 200 ms. An LLM used as a detector, several hundred milliseconds. A thread pipeline caches each message's detections, so resending a message inside a thread skips detection. Measuring on your actual workload remains recommended before sizing production.

??? question "Does `piighost` work 100% offline?"
    Yes. With a local detector (`gliner2`, `spacy`, `regex`, `exact`), no data leaves your process. The middleware only forwards already de-identified text to the LLM. This is the main reason teams adopt `piighost`, keeping a hosted LLM under GDPR constraints without exfiltrating raw PII. See [Why de-identify?](../why-anonymize.md) for the legal context.

??? question "Do my placeholders have to look like `<<PERSON:1>>`?"
    No. The format is driven by the placeholder factory chosen in `[anonymizer.placeholder]`. `label_counter` produces `<<PERSON:1>>`{ .placeholder }, `label_hash` produces `<<PERSON:a1b2c3d4>>`{ .placeholder }, `label` produces `<<PERSON>>`{ .placeholder } without a counter, `mask` produces `P***`{ .placeholder }, and you can write your own factory. See [Placeholder factories](../placeholder-factories.md).

??? question "Can I get realistic fake values instead of tokens?"
    Not yet. A Faker factory that emits realistic values (a plausible name in place of `Patrick`{ .pii }) is on the [roadmap](../roadmap.md) but not reimplemented in v2. Today the factories emit synthetic tokens or masks, never a value that looks real.

??? question "Does the LLM see raw PII when it calls a tool?"
    It depends on the tool-call strategy. With the default (`FULL`), no. The middleware restores arguments right before the tool executes, then re-de-identifies the tool response before it flows back to the LLM. The tool sees real values, the LLM only sees placeholders. The `INPUT`, `OUTPUT` and `PASSTHROUGH` modes change this behaviour, see the next question and [Tool-call strategies](../tool-call-strategies.md). Full diagram in [Architecture](../architecture.md).

??? question "How do I control what a tool sees: placeholder or real value?"
    The tool-call strategy of `PIIAnonymizationMiddleware` exposes four modes (`INPUT`, `OUTPUT`, `FULL`, `PASSTHROUGH`). The right choice depends on whether the tool may emit new PII and how strict the privacy boundary needs to be. See [Tool-call strategies](../tool-call-strategies.md) for the trade-offs and the decision tree, and [Placeholder factories](../placeholder-factories.md) for the factory constraint, the middleware needs an identity-preserving, recognizable placeholder factory.

??? question "What happens if the LLM hallucinates a PII that was not in the input?"
    It is **not** de-identified by `piighost`: entity linking works on detections coming from the input, not on invented values. A residual-PII guard can re-check the output and refuse it, see the guard section of the [configuration reference](../configuration/toml.md) and [Limitations](../limitations.md).

??? question "Is the conversation memory shared across threads?"
    No. The memory is scoped by `thread_id`. Two parallel conversations never see each other's tokens, preventing cross-user leaks. The `thread_id` is extracted automatically from the LangGraph config.

??? question "How do I run more than one worker behind a load balancer?"
    Use the Redis conversation memory, shared by every worker. The in-RAM memory is process-local, so two workers would number the same value differently mid-conversation. See [Multi-instance deployment](../multi-instance.md) for the trap and the fix, and [Deploy a production pipeline](../deployment.md) for the full setup.

??? question "Can I use `piighost` without LangChain?"
    Yes. The stateless and thread pipelines are usable standalone, without the middleware. See [Basic usage](../examples/basic.md).

??? question "Does `piighost` encrypt stored data?"
    The Redis conversation memory does: it encrypts every stored value with AES-GCM and hashes every key, reading its pepper and cipher key from the environment. The in-RAM memory encrypts nothing and is for development only. See [Security](../security.md) for the at-rest threat model.

??? question "How do I trace what the pipeline does?"
    Through OpenTelemetry. The pipeline emits a span per stage to whatever OTel `TracerProvider` your application configured, and does no backend correlation itself, that is deployment OTel configuration. See [Observation](../observation.md). The `observation` extra is required.
