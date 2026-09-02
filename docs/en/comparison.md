---
icon: lucide/scale
---

# How PIIGhost compares

This table is not neutral: the rows are the capabilities PIIGhost was built for, so it naturally comes out ahead. It is here to show what most other tools leave out, not to declare a winner. For a job PIIGhost is not built for, such as releasing a whole dataset, a k-anonymity tool is the right choice.

| Capability | **PIIGhost** | Presidio | LangChain PII | Cloud (AWS/Azure) | Google DLP | pii-redactor |
|---|---|---|---|---|---|---|
| **Detection** | regex / NER / LLM | NER + regex + rules + checksum | regex + validators | ML/NER | ML + infoTypes | regex + NER |
| **PII handling** | reversible token (memory/Redis) | mask / token | mask / hash | mask | crypto token (stateless) | reversible token (vault) |
| **Transparent restore for the user** | ✅ | ⚠️ manual (`decrypt`) | ❌ | ❌ | ⚠️ re-id via API | ✅ |
| **Consistent across a conversation** | ✅ per thread | ❌ | ❌ | ❌ | ✅ deterministic | ✅ per session |
| **Tool boundary** (tool gets the real value, LLM gets the token) | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Streaming** (token-by-token restore) | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ |
| **Configurable post-detection stages** (linking, fuzzy, expansion, guard) | ✅ | ⚠️ operators only | ❌ | ❌ | ⚠️ transforms | ❌ |
| **Unit processed** | text / conversation | text | text / conversation | text / documents | text / dataset | text / conversation |
| **Self-hosted (OSS)** | ✅ | ✅ | ✅ | ❌ cloud | ❌ cloud | ✅ |
| **License** | MIT | MIT | MIT | Commercial | Commercial | MIT |

Notes: **LangChain PII** here is the Python `PIIMiddleware`. The JS `piiRedactionMiddleware` is the opposite trade-off, reversible but no streaming. **Cloud** groups AWS Comprehend and Azure AI Language, and Azure's Conversation mode only detects, it does not restore.

Detection-only models (spaCy, GLiNER, Piiranha) and dataset anonymizers (ARX, Amnesia) sit in a different category. The first only find PII, the second transform a whole tabular dataset with k-anonymity or differential privacy, so they are not de-identifying a live conversation.

See [Limitations](limitations.md) for what PIIGhost does not do and the trade-offs behind these choices.
