---
icon: lucide/message-circle-question
---

# FAQ

??? question "Is it really necessary to anonymize PII before calling an LLM?"
    Yes, and this holds regardless of `piighost`. The stakes (exfiltration to providers, legal requisition, training on conversations, GDPR compliance, data leaks) are covered in [Why anonymize?](../why-anonymize.md). The page is library-agnostic: it explains why the problem exists before justifying a solution like `piighost`.

??? question "Which languages are supported?"
    It depends entirely on the detector you plug in. The pipeline itself is language-agnostic. With `Gliner2Detector` and a multilingual GLiNER2 model, you get about 100 languages out of the box. With a spaCy detector, whatever spaCy supports. With `RegexDetector`, language is irrelevant. See [Extending PIIGhost](../extending.md) for the detector catalogue.

??? question "Which entities are detected out of the box?"
    None. `piighost` does not ship its own NER model, this is a deliberate design choice. You bring the detector. Use `ExactMatchDetector` for fixed dictionaries, `RegexDetector` with `piighost.detector.patterns` (FR_IBAN, FR_NIR, EU_VAT…), `Gliner2Detector` for open NER (`PERSON`, `LOCATION`, `ORGANIZATION`, `EMAIL`, any label you ask for), or compose them via `CompositeDetector`.

??? question "What latency does the pipeline add?"
    The pipeline itself is on the millisecond scale (regex and lookups). The real cost comes from the detector. GLiNER2 on CPU for a 200-token message is typically 50 to 200 ms. An LLM used as a detector, several hundred milliseconds. The pipeline caches detections by text hash via `aiocache`, so repeated content is free. Measuring on your actual workload remains recommended before sizing production.

??? question "Does `piighost` work 100% offline?"
    Yes. With a local detector (`Gliner2Detector`, spaCy detector, `RegexDetector`, `ExactMatchDetector`), no data leaves your process. The middleware only forwards already-anonymized text to the LLM. This is the main reason teams adopt `piighost`, keeping a hosted LLM under GDPR constraints without exfiltrating raw PII. See [Why anonymize?](../why-anonymize.md) for the legal context.

??? question "Do my placeholders have to look like `<<PERSON:1>>`?"
    No. The format is driven by `AnyPlaceholderFactory`. By default `LabelCounterPlaceholderFactory` produces `<<LABEL:N>>`, but `LabelHashPlaceholderFactory` yields `<<LABEL:hash>>`, `LabelPlaceholderFactory` produces `<<LABEL>>` without a counter, and you can write your own factory. See [Placeholder factories](../placeholder-factories.md).

??? question "Does the LLM see raw PII when it calls a tool?"
    It depends on `tool_strategy`. With the default (`FULL`), no. The middleware deanonymizes arguments right before the tool executes, then re-anonymizes the tool response before it flows back to the LLM. The tool sees real values; the LLM only sees placeholders. The `INBOUND_ONLY` and `PASSTHROUGH` modes change this behaviour, see the next question and [Tool-call strategies](../tool-call-strategies.md). Full diagram in [Architecture](../architecture.md).

??? question "How do I control what a tool sees: placeholder or real value?"
    The `tool_strategy` parameter of `PIIAnonymizationMiddleware` exposes three modes (`FULL`, `INBOUND_ONLY`, `PASSTHROUGH`) via the `ToolCallStrategy` enum. The right choice depends on whether the tool may emit new PII and how strict the privacy boundary needs to be. See [Tool-call strategies](../tool-call-strategies.md) for the trade-offs and the decision tree, and [Placeholder factories](../placeholder-factories.md) for the factory constraint that forces `PreservesIdentity` in every mode but `PASSTHROUGH`.

??? question "What happens if the LLM hallucinates a PII that was not in the input?"
    It is **not** anonymized by `piighost`: entity linking works on detections coming from the input, not on invented values. To cover that case, add a post-response detection pass at the application layer. See [Limitations](../limitations.md).

??? question "Is the cache shared across threads or conversations?"
    No. The `aiocache` cache is scoped by `thread_id`. Two parallel conversations never see each other's placeholders, preventing cross-user leaks. The `thread_id` is extracted automatically from the LangGraph config.

??? question "Can I use `piighost` without LangChain?"
    Yes. `AnonymizationPipeline` and `ThreadAnonymizationPipeline` are usable standalone, without the middleware. See [Basic usage](../examples/basic.md).

??? question "Does `piighost` encrypt cached data?"
    No. The cache stores the `placeholder → value` mapping in memory (or in the `aiocache` backend you configured). See [Security](../security.md) for the full list of things out of scope.
