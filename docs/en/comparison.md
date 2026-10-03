---
icon: lucide/scale
---

# How PIIGhost compares

`piighost` combines four properties a conversational agent needs: restore the reply for the user, keep the same placeholder over the whole conversation, hand the real value to tools, and restore while the reply streams. None of the tools below combines all four. Each one is better than `piighost` at something else, and its entry says what.

Open a solution to see how it differs from `piighost`.

??? note "`piighost`, its choices and its limits"

    - Detects with regexes, NER models (GLiNER2, spaCy, Transformers, Presidio) or an LLM, alone or combined.
    - Replaces each value with a reversible placeholder, the same over the whole conversation, kept in memory or in Redis.
    - Restores the reply for the user, while it streams too, and hands the real value to the agent's tools.
    - Choice: no checksum validation (Luhn, IBAN check digits). A value damaged by OCR is still detected, at the cost of false positives.
    - Choice: de-identification is reversible. Under the GDPR it is pseudonymization, and the mapping is personal data to protect.
    - Does not: guarantee that no value escapes. A detector misses values, and a guard rail only flags them.
    - Does not: restore a value the LLM makes up, or share the memory between processes without Redis.
    - Does not: transform a whole dataset. The added latency is not measured yet.

??? note "Presidio (Microsoft, MIT)"

    - Detects with NER, regexes, rules and check digits.
    - Masks, or replaces with an encrypted token.
    - Restores only by hand, with `decrypt`.
    - Does not keep the same token from one message to the next.
    - Nothing for tools or for streaming.
    - Better at: validating a format by its check digits, on typed text.
    - `piighost` can use it as a detector, with `PresidioDetector`.

??? note "LangChain PII (`PIIMiddleware`, MIT)"

    - Detects with regexes and validators.
    - Masks or hashes, with no restoration for the user.
    - Protects the tool boundary and the stream.
    - Keeps no placeholder over the conversation.
    - The JS version (`piiRedactionMiddleware`) makes the opposite trade-off: it restores, without streaming.
    - Better at: nothing more to install in a LangChain agent, when the user does not need to read their real values.

??? note "AWS Comprehend and Azure AI Language (cloud, paid)"

    - Detect with machine learning and mask.
    - No restoration. Azure's Conversation mode only detects.
    - Nothing for the conversation, tools or streaming.
    - The text goes to the cloud provider.
    - Better at: models the provider maintains, to mask documents in a cloud already in place.

??? note "Google DLP (cloud, paid)"

    - Detects with machine learning and predefined types (infoTypes).
    - Replaces with a stateless encrypted token, always the same for the same value.
    - Restores through an API call.
    - Nothing for tools or streaming.
    - The text goes to Google.
    - Better at: transforming whole datasets in Google Cloud.

??? note "pii-redactor (MIT)"

    - The closest to `piighost`.
    - Detects with regexes and NER.
    - Replaces with a reversible token kept in a vault, the same over the session, and restores while streaming.
    - Does not hand the real value to tools.
    - No configurable step after detection (linking, fuzzy matching, expansion, guard rail).

??? note "Detection-only models (spaCy, GLiNER, Piiranha)"

    - Find the data without replacing or restoring it.
    - Building blocks rather than competitors: `piighost` uses them as detectors, Piiranha through `TransformersDetector`.

??? note "Dataset anonymizers (ARX, Amnesia)"

    - Transform a whole table with k-anonymity or differential privacy.
    - The result is anonymous and irreversible, where `piighost` is reversible.
    - Better at: publishing or sharing a dataset. Not made for a live conversation.

See [Limitations](limitations.md) for what `piighost` does not do, and the reasoning behind these choices.
