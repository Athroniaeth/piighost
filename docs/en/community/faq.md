---
icon: lucide/message-circle-question
---

# FAQ

??? question "Is it really necessary to anonymize PII before calling an LLM?"
    Yes, and this holds regardless of `piighost`. The stakes (exfiltration to providers, legal requisition, training on conversations, GDPR compliance, leaks via RAG and tools) are covered in [Why anonymize?](../why-anonymize.md). The page is library-agnostic: it explains why the problem exists before justifying a solution like `piighost`.

??? question "Do my placeholders have to look like `<<PERSON_1>>`?"
    No. The format is driven by `AnyPlaceholderFactory`. By default `CounterPlaceholderFactory` produces `<<LABEL_N>>`, but `HashPlaceholderFactory` yields opaque deterministic tags, `RedactPlaceholderFactory` produces `<LABEL>` without a counter, and you can write your own factory. See [Extending PIIGhost](../extending.md).

??? question "Does the LLM see raw PII when it calls a tool?"
    No. The middleware deanonymizes arguments right before the tool executes, then re-anonymizes the tool response before it flows back to the LLM. The tool sees real values; the LLM only sees placeholders. See the sequence diagram in [Architecture](../architecture.md).

??? question "How do I control what a tool sees: placeholder or real value?"
    The `tool_strategy` parameter of `PIIAnonymizationMiddleware` exposes three modes via the `ToolCallStrategy` enum:

    - `FULL` (default): the tool receives real values and its response is re-anonymized immediately through the full pipeline. Use for tools whose output may contain new PII (databases, CRMs, web search).
    - `INBOUND_ONLY`: the tool receives real values; its response flows through raw and is re-anonymized lazily on the next `abefore_model` pass. Cheaper when the output does not introduce new PII.
    - `PASSTHROUGH`: the tool receives placeholders verbatim. Use when no PII must ever leave the middleware, or when the agent's tools simply don't need it.

    The choice of `PlaceholderFactory` matters: `HashPlaceholderFactory` is the safest (deterministic, near-zero collisions), `CounterPlaceholderFactory` works well within a thread, and `FakerPlaceholderFactory` can collide with real values. `RedactPlaceholderFactory` and `MaskPlaceholderFactory` are rejected at construction time by `ThreadAnonymizationPipeline`.

    The rule is expressed in the **preservation tag** each factory carries (`PreservesIdentity`, `PreservesLabel`, `PreservesShape`, `PreservesNothing`). `PIIAnonymizationMiddleware` only accepts a `ThreadAnonymizationPipeline[PreservesIdentity]`, so mixing it with a weaker factory is flagged by your type checker before you even run the code. See [Extending PIIGhost](../extending.md) for details.

??? question "What happens if the LLM hallucinates a PII that was not in the input?"
    It is **not** anonymized by `piighost`: entity linking works on detections coming from the input, not on invented values. To cover that case, add a post-response detection pass at the application layer. See [Limitations](../limitations.md).

??? question "Is the cache shared across threads or conversations?"
    No. The `aiocache` cache is scoped by `thread_id`. Two parallel conversations never see each other's placeholders, preventing cross-user leaks. The `thread_id` is extracted automatically from the LangGraph config.

??? question "Can I use `piighost` without LangChain?"
    Yes. `AnonymizationPipeline` and `ThreadAnonymizationPipeline` are usable standalone, without the middleware. See [Basic usage](../examples/basic.md).

??? question "Does `piighost` encrypt cached data?"
    No. The cache stores the `placeholder → value` mapping in memory (or in the `aiocache` backend you configured). See [Security](../security.md) for the full list of things out of scope.
