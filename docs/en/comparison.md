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

??? note "Presidio (Microsoft)"

    | | `piighost` | Presidio |
    |---|---|---|
    | Detection | regex, NER or LLM | NER, regex, rules, check digits |
    | What happens to a value | reversible placeholder (memory or Redis) | mask or encrypted token |
    | Restored for the user | ✅ | ⚠️ by hand (`decrypt`) |
    | Same placeholder over the conversation | ✅ per conversation | ❌ |
    | Real value to tools, placeholder to the LLM | ✅ | ❌ |
    | Restored while streaming | ✅ | ❌ |
    | Configurable steps after detection | ✅ linking, fuzzy matching, expansion, guard rail | ⚠️ operators only |
    | Unit processed | text, conversation | text |
    | Hosting | ✅ self-hosted | ✅ self-hosted |
    | License | MIT | MIT |

    **Better at**: validating a format by its check digits, on typed text. `piighost` can also use it as a detector, with `PresidioDetector`.

??? note "LangChain PII (Python `PIIMiddleware`)"

    | | `piighost` | LangChain PII |
    |---|---|---|
    | Detection | regex, NER or LLM | regex, validators |
    | What happens to a value | reversible placeholder (memory or Redis) | mask or hash |
    | Restored for the user | ✅ | ❌ |
    | Same placeholder over the conversation | ✅ per conversation | ❌ |
    | Real value to tools, placeholder to the LLM | ✅ | ✅ |
    | Restored while streaming | ✅ | ✅ |
    | Configurable steps after detection | ✅ linking, fuzzy matching, expansion, guard rail | ❌ |
    | Unit processed | text, conversation | text, conversation |
    | Hosting | ✅ self-hosted | ✅ self-hosted |
    | License | MIT | MIT |

    **Better at**: there is nothing more to install in a LangChain agent. That is enough when the user does not need to read their real values. The JS version (`piiRedactionMiddleware`) restores the real values for the user, but not while the reply streams.

??? note "AWS Comprehend and Azure AI Language"

    | | `piighost` | AWS / Azure |
    |---|---|---|
    | Detection | regex, NER or LLM | machine learning |
    | What happens to a value | reversible placeholder (memory or Redis) | mask |
    | Restored for the user | ✅ | ❌ |
    | Same placeholder over the conversation | ✅ per conversation | ❌ |
    | Real value to tools, placeholder to the LLM | ✅ | ❌ |
    | Restored while streaming | ✅ | ❌ |
    | Configurable steps after detection | ✅ linking, fuzzy matching, expansion, guard rail | ❌ |
    | Unit processed | text, conversation | text, documents |
    | Hosting | ✅ self-hosted | ❌ cloud |
    | License | MIT | paid |

    **Better at**: models the provider maintains, to mask documents in a cloud already in place. Azure's Conversation mode only detects.

??? note "Google DLP"

    | | `piighost` | Google DLP |
    |---|---|---|
    | Detection | regex, NER or LLM | machine learning, predefined types (infoTypes) |
    | What happens to a value | reversible placeholder (memory or Redis) | stateless encrypted token |
    | Restored for the user | ✅ | ⚠️ through an API call |
    | Same placeholder over the conversation | ✅ per conversation | ✅ always the same token for a value |
    | Real value to tools, placeholder to the LLM | ✅ | ❌ |
    | Restored while streaming | ✅ | ❌ |
    | Configurable steps after detection | ✅ linking, fuzzy matching, expansion, guard rail | ⚠️ transformations |
    | Unit processed | text, conversation | text, dataset |
    | Hosting | ✅ self-hosted | ❌ cloud |
    | License | MIT | paid |

    **Better at**: transforming whole datasets in Google Cloud.

??? note "pii-redactor"

    | | `piighost` | pii-redactor |
    |---|---|---|
    | Detection | regex, NER or LLM | regex, NER |
    | What happens to a value | reversible placeholder (memory or Redis) | reversible token (vault) |
    | Restored for the user | ✅ | ✅ |
    | Same placeholder over the conversation | ✅ per conversation | ✅ per session |
    | Real value to tools, placeholder to the LLM | ✅ | ❌ |
    | Restored while streaming | ✅ | ✅ |
    | Configurable steps after detection | ✅ linking, fuzzy matching, expansion, guard rail | ❌ |
    | Unit processed | text, conversation | text, conversation |
    | Hosting | ✅ self-hosted | ✅ self-hosted |
    | License | MIT | MIT |

    **Note**: it is the closest to `piighost`. It lacks the real value to tools and the configurable steps.

??? note "Detection-only models (spaCy, GLiNER, Piiranha)"

    - Find the data without replacing or restoring it.
    - Building blocks rather than competitors: `piighost` uses them as detectors, Piiranha through `TransformersDetector`.

??? note "Dataset anonymizers (ARX, Amnesia)"

    - Transform a whole table with k-anonymity or differential privacy.
    - The result is anonymous and irreversible, where `piighost` is reversible.
    - Better at: publishing or sharing a dataset. Not made for a live conversation.

See [Limitations](limitations.md) for what `piighost` does not do, and the reasoning behind these choices.
