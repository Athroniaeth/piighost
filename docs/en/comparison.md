---
icon: lucide/scale
description: Compare piighost with Presidio, LangChain PII middleware, LLM Guard and cloud DLP, and find the Presidio alternative that restores PII in LLM replies.
seo_title: piighost vs Presidio, LangChain PII and LLM Guard, compared
---

# How piighost compares

`piighost` combines four properties a conversational agent needs. It restores the reply for the user, keeps the same placeholder over the whole conversation, hands the real value to tools, and restores while the reply streams. None of the tools below documents all four together. Each one is better than `piighost` at something else, and its section says what.

## Summary

Last checked: 6 October 2026.

<div class="wide-table" markdown="1">

| Tool | Restores values in the reply | Restores tool-call arguments | Same placeholder across a conversation | Streaming | Framework integrations | License | Status |
|---|---|---|---|---|---|---|---|
| `piighost` | ✅ | ✅ | ✅ per conversation | ✅ restores as the reply streams | LangChain, Pydantic AI, LlamaIndex, Claude Code, OpenAI and Anthropic proxy (`piighost-api`) | MIT | active |
| [Presidio](#piighost-vs-presidio) | ⚠️ by hand (`decrypt`) | ❌ | ❌ | ❌ | none, a library and a REST service | MIT | active, under Data Privacy Stack |
| [`PresidioReversibleAnonymizer`](#piighost-vs-presidioreversibleanonymizer) | ✅ | ❌ | ⚠️ one mapping per anonymizer object | ❌ | LangChain chains | MIT | archived, 22 May 2026 |
| [LangChain `PIIMiddleware` (Python)](#piighost-vs-langchain-pii-middleware) | ❌ | ❌ | ⚠️ with the `hash` strategy | ❌ masks the stream | LangChain agents | MIT | active |
| [LangChain `piiRedactionMiddleware` (JS)](#piighost-vs-langchain-pii-middleware) | ✅ after the model call | ✅ | ❌ a new marker per occurrence | ❌ | LangChain.js agents | MIT | deprecated |
| [LLM Guard](#piighost-vs-llm-guard) | ✅ | not documented | ⚠️ while the same vault is reused | not documented | library, API server | MIT | archived, 9 July 2026 |
| [AWS Comprehend, Azure AI Language](#piighost-vs-aws-comprehend-and-azure-ai-language) | ❌ | ❌ | ❌ | ❌ | cloud API | paid | active |
| [Google DLP](#piighost-vs-google-dlp) | ⚠️ through an API call | ❌ | ✅ always the same token for a value | ❌ | cloud API | paid | active |
| [PrivAiTe](#piighost-vs-privaite) | ✅ | ✅ | ⚠️ per request | ✅ | OpenAI-compatible proxy, Claude Code and Codex gateway, Open WebUI, LiteLLM | BSD-3-Clause | active |
| [Etalab `pseudo_api`](#piighost-vs-etalab-pseudo_api) | ❌ | ❌ | n/a, one document at a time | ❌ | REST API | MIT | archived |

</div>

Detection-only models and dataset anonymizers are not in the table, because they do not replace and restore values in a conversation. Their sections are at the end of the page.

## `piighost` vs Presidio

[Presidio](https://github.com/data-privacy-stack/presidio) detects personal data and replaces it with operators. It left Microsoft in 2026 and is now a community project under the [Data Privacy Stack](https://github.com/data-privacy-stack/presidio/blob/main/docs/project_transition.md) organization, still under the MIT license. Its [anonymizer](https://presidio.dataprivacystack.org/anonymizer/) can revert only an encrypted value, with the `decrypt` operator.

| | `piighost` | Presidio |
|---|---|---|
| Detection | regex, NER or LLM | NER, regex, rules, check digits |
| What happens to a value | reversible placeholder (memory, Redis or SQL) | mask or encrypted token |
| Restored for the user | ✅ | ⚠️ by hand (`decrypt`) |
| Same placeholder over the conversation | ✅ per conversation | ❌ |
| Real value to tools, placeholder to the LLM | ✅ | ❌ |
| Restored while streaming | ✅ | ❌ |
| Configurable steps after detection | ✅ linking, fuzzy matching, expansion, guard rail | ⚠️ operators only |
| Unit processed | text, conversation | text |
| Hosting | ✅ self-hosted | ✅ self-hosted |
| License | MIT | MIT |

**Better at**: validating a format by its check digits, on typed text. `piighost` can also use it as a detector, with `PresidioDetector`.

## `piighost` vs PresidioReversibleAnonymizer

`PresidioReversibleAnonymizer` wraps Presidio in a LangChain object with `anonymize()` and `deanonymize()` methods. It lived in the `langchain-experimental` package, which LangChain [sunset](https://github.com/langchain-ai/langchain-experimental/issues/87) on 22 May 2026. The [repository](https://github.com/langchain-ai/langchain-experimental) is archived, so the class gets no more fixes.

- It replaces each value with a fake one from Faker by default, then restores it from a mapping kept in the object.
- One object holds one mapping for every text it sees, so two conversations share it unless you reset it.
- It restores neither tool-call arguments nor a streamed reply.

**Better at**: it was a one-line addition to a LangChain chain that already used Presidio. To move that chain to `piighost`, see [Migrate from PresidioReversibleAnonymizer](examples/migrate-from-presidio-reversible-anonymizer.md).

## `piighost` vs LangChain PII middleware

The Python [`PIIMiddleware`](https://docs.langchain.com/oss/python/langchain/middleware/built-in#pii-detection) blocks, redacts, masks or hashes a value in an agent's messages. Its [source](https://github.com/langchain-ai/langchain/blob/master/libs/langchain_v1/langchain/agents/middleware/pii.py) also masks the streamed output. It never restores a value, so a tool receives what the model wrote.

| | `piighost` | LangChain PII |
|---|---|---|
| Detection | regex, NER or LLM | regex, validators |
| What happens to a value | reversible placeholder (memory, Redis or SQL) | mask or hash |
| Restored for the user | ✅ | ❌ |
| Same placeholder over the conversation | ✅ per conversation | ⚠️ with the `hash` strategy |
| Real value to tools, placeholder to the LLM | ✅ | ❌ |
| Restored while streaming | ✅ | ❌ masks the stream |
| Configurable steps after detection | ✅ linking, fuzzy matching, expansion, guard rail | ❌ |
| Unit processed | text, conversation | text, conversation |
| Hosting | ✅ self-hosted | ✅ self-hosted |
| License | MIT | MIT |

The JavaScript [`piiRedactionMiddleware`](https://reference.langchain.com/javascript/langchain/index/piiRedactionMiddleware) restored the values after the model call, in the reply and in [tool-call arguments](https://github.com/langchain-ai/langchainjs/blob/main/libs/langchain/src/agents/middleware/piiRedaction.ts). It gives each occurrence a new random marker, and it restores only once the model call ends. It is now marked deprecated, and LangChain [moved its docs](https://github.com/langchain-ai/docs/pull/6366) to `piiMiddleware`, which blocks, redacts, masks or hashes without restoring.

**Better at**: there is nothing more to install in a LangChain agent. That is enough when the user does not need to read their real values.

## `piighost` vs LLM Guard

[LLM Guard](https://github.com/protectai/llm-guard) was archived on 9 July 2026 and is no longer maintained. `piighost` covers only its [Anonymize](https://protectai.github.io/llm-guard/input_scanners/anonymize/) and [Deanonymize](https://protectai.github.io/llm-guard/output_scanners/deanonymize/) scanners, which replace values and restore them from a [vault](https://github.com/protectai/llm-guard/blob/main/llm_guard/input_scanners/anonymize.py). `piighost` has no equivalent of the other scanners, such as prompt injection, toxicity or banned topics.

## `piighost` vs AWS Comprehend and Azure AI Language

[AWS Comprehend](https://docs.aws.amazon.com/comprehend/latest/dg/how-pii.html) and [Azure AI Language](https://learn.microsoft.com/en-us/azure/ai-services/language-service/personally-identifiable-information/overview) detect personal data and return a masked text from a cloud API.

| | `piighost` | AWS / Azure |
|---|---|---|
| Detection | regex, NER or LLM | machine learning |
| What happens to a value | reversible placeholder (memory, Redis or SQL) | mask |
| Restored for the user | ✅ | ❌ |
| Same placeholder over the conversation | ✅ per conversation | ❌ |
| Real value to tools, placeholder to the LLM | ✅ | ❌ |
| Restored while streaming | ✅ | ❌ |
| Configurable steps after detection | ✅ linking, fuzzy matching, expansion, guard rail | ❌ |
| Unit processed | text, conversation | text, documents |
| Hosting | ✅ self-hosted | ❌ cloud |
| License | MIT | paid |

**Better at**: models the provider maintains, to mask documents in a cloud already in place.

## `piighost` vs Google DLP

Google's Sensitive Data Protection, formerly Cloud DLP, can [pseudonymize](https://cloud.google.com/sensitive-data-protection/docs/pseudonymization) a value with a key and re-identify it through a second API call.

| | `piighost` | Google DLP |
|---|---|---|
| Detection | regex, NER or LLM | machine learning, predefined types (infoTypes) |
| What happens to a value | reversible placeholder (memory, Redis or SQL) | stateless encrypted token |
| Restored for the user | ✅ | ⚠️ through an API call |
| Same placeholder over the conversation | ✅ per conversation | ✅ always the same token for a value |
| Real value to tools, placeholder to the LLM | ✅ | ❌ |
| Restored while streaming | ✅ | ❌ |
| Configurable steps after detection | ✅ linking, fuzzy matching, expansion, guard rail | ⚠️ transformations |
| Unit processed | text, conversation | text, dataset |
| Hosting | ✅ self-hosted | ❌ cloud |
| License | MIT | paid |

**Better at**: transforming whole datasets in Google Cloud.

## `piighost` vs PrivAiTe

[PrivAiTe](https://github.com/crp4222/PrivAiTe) is a self-hosted proxy that sits between an application and the model provider. It replaces values in messages and in tool-call arguments, then restores them in the reply, streaming included.

- It keeps the mapping for one request and drops it when the request ends. A chat client resends the whole history, so numbering stays consistent within each request.
- It plugs in as an OpenAI-compatible proxy, a gateway for Claude Code and Codex, an Open WebUI filter or a LiteLLM guardrail.
- It is a proxy, so it does not run inside an agent framework the way a middleware does.

**Better at**: covering an agent CLI or an existing OpenAI-compatible app without touching its code, with a published leak benchmark.

## `piighost` vs Etalab `pseudo_api`

[`pseudo_api`](https://github.com/etalab-ia/pseudo_api) is the pseudonymization API of the Lab IA of Etalab, part of the French interministerial digital directorate (DINUM). It replaces first names, last names and addresses in court decisions of the Conseil d'État, so they can be published. It has no endpoint that restores a value, and the repository is archived.

**Note**: it shows the French administration's approach, which pseudonymizes a document for good before publishing it. The repository does not ship its trained model, because the training data are not public.

## Detection-only models

spaCy, GLiNER, Piiranha and [OpenAI Privacy Filter](https://github.com/openai/privacy-filter), released on 22 April 2026 under Apache-2.0, find the data. At most they mask it, and they never restore it.

- They are building blocks rather than competitors. `piighost` uses spaCy, GLiNER and Piiranha as detectors, Piiranha through `TransformersDetector`.

## Dataset anonymizers

ARX and Amnesia transform a whole table with k-anonymity or differential privacy.

- The result is anonymous and irreversible, where `piighost` is reversible.
- Better at: publishing or sharing a dataset. Not made for a live conversation.

See [Limitations](limitations.md) for what `piighost` does not do, and the reasoning behind these choices. For the vocabulary used on this page, see [Anonymization, pseudonymization, redaction, masking](anonymization-vs-pseudonymization.md).
